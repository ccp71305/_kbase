# Step 1a — root pom (`WI01124532-aws-sdk-upgrade-pom`)

← [Tracker home](../README.md) · [All steps](README.md)


**Plan:**

1. `WI01124532 build:` Surefire on the JUnit Platform: remove the root `surefire-junit4` provider; add `junit-jupiter` + `junit-vintage-engine` (test scope, versions from the Dropwizard 5.0.2 JUnit BOM, 5.14.4) for the root pom's children. Proof: per-module test counts equal the baseline (transformer increases, [F2](../closed-items.md#f2)).
2. `WI01124532 red:` `shared` `PlatformLibraryVersionsTest` (JUnit 5 + AssertJ), failing on today's pins.
3. `WI01124532 green:` align the root pins with commons 1.0.38; pin `logback-core` together with `logback-classic`; add `mercury.commons.version` and `dependencyManagement` entries for `commons`, `cloud-sdk-api`, `cloud-sdk-aws`; remove gen2-parser's local logback/slf4j overrides.
4. `WI01124532 refactor:` tidy the root pom (duplicate `dropwizard.metrics.annotation` property, unused `shared` `jackson-datatype-jsr310-version`).
5. `dependency:tree` per service in the PR description (acceptance criterion 5).

**Baseline (`develop` `0448d362`):** first run failed at `registration-inbound-consumers` ([F1](../findings.md#f1)); re-run with [G2](../rules.md#g2): **BUILD SUCCESS, 26 modules, 9:05 min**. Tests / skipped per module:

| Module | Tests | Skipped |
|---|---|---|
| watermill/billoflading/ebl-inbound-consumers | 10 | 0 |
| watermill/billoflading/registration-inbound-consumers | 10 | 0 |
| watermill/booking-inbound-consumer | 173 | 0 |
| watermill/cargoscreen-consumer | 0 | 0 ([F3](../findings.md#f3)) |
| watermill/itv-gps-consumer | 80 | 0 |
| watermill/visibility-inbound-consumer | 318 | 0 |
| shared | 1510 | 1 |
| structuralvalidator | 239 | 10 |
| gen2-parser | 1726 | 0 |
| event-writer | 3 | 0 |
| dispatcher | 15 | 0 |
| splitter | 179 | 2 |
| transformer | 4 | 4 ([F2](../closed-items.md#f2)) |
| distributor | 48 | 4 |
| distributor-rest | 142 | 0 |
| ingestor | 179 | 0 |
| error-processor | 2 | 0 |
| email-sender | 13 | 0 |
| watermill-publisher | 153 | 0 |
| watermill/consumer-commons | 149 | 0 |
| watermill/consumer-framework | 38 | 0 |

**Key class: `com.inttra.mercury.shared.support.PlatformLibraryVersionsTest` (test, JUnit 5):**

| Method | Asserts |
|---|---|
| `jacksonIsAtLeastTheCommonsVersion` | `jackson-databind`, `jackson-core` ≥ 2.21.8 |
| `jettyIsAtLeastTheCommonsVersion` | `jetty-server` ≥ 12.1.14 |
| `logbackIsAtLeastTheCommonsVersion` | `logback-classic` ≥ 1.5.38 |
| `logbackClassicAndCoreAreTheSameVersion` | `logback-core` = `logback-classic` (a mismatched pair fails at runtime) |
| `slf4jIsAtLeastTheCommonsVersion` | `slf4j-api` ≥ 2.0.18 |
| `httpCore5IsAtLeastTheCommonsVersion` | `httpcore5` ≥ 5.4.3 |
| `dropwizardIsTheCommonsVersion` | `dropwizard-core` = 5.0.2 |
| `versionOf(groupId, artifactId)` (helper) | Reads the resolved version from the jar's `META-INF/maven/<groupId>/<artifactId>/pom.properties` on the test classpath; compares with `Runtime.Version` (numeric, not string, ordering) |

**Commits:**

| # | Commit | Type | Files | Result |
|---|---|---|---|---|
| 1 | `701cc85c` WI01124532 build: run tests on the JUnit Platform (Jupiter + Vintage) | build | `pom.xml` | Full reactor green (9:14 min). Test counts identical to the baseline for every module except transformer: **4 → 665 tests (5 skipped), all passing** ([F2](../closed-items.md#f2) resolved, [A14](../closed-items.md#a14) done) |
| 2 | `42593970` WI01124532 red: platform library versions must not be below commons 1.0.38 | red | `shared/.../support/PlatformLibraryVersionsTest.java` | 7 tests, **4 fail** (Jackson 2.21.4, Jetty 12.1.9, logback 1.5.33, slf4j 2.0.17); logback pair, httpcore5, Dropwizard pass |
| 3 | `3f27f8e7` WI01124532 green: align platform pins with commons 1.0.38 | green | `pom.xml`, `gen2-parser/pom.xml` | `PlatformLibraryVersionsTest` 7/7 pass; full reactor green (9:24 min); counts unchanged except `shared` +7 |
| 4 | `9b0a1235` WI01124532 refactor: tidy platform pin comments and unused properties | refactor | `pom.xml`, `shared/pom.xml` | Stale ION-16098 version comments updated; duplicate `dropwizard.metrics.annotation` and unused `jackson-datatype-jsr310-version` removed; reactor `validate` + `shared` 1517 tests green |
| 5 | `fb837d9d` WI01124532 red: enforce one logback-classic/logback-core version per module | red | `pom.xml` | `dependency:tree` showed watermill-publisher on classic 1.5.33 / core 1.5.38 ([F5](../closed-items.md#f5)). New `maven-enforcer-plugin` 3.4.1 `requireSameVersions` rule fails watermill-publisher only |
| 6 | `6bb9ae6c` WI01124532 green: watermill-publisher takes logback from the root pins | green | `watermill-publisher/pom.xml` | Hardcoded `logback-classic` 1.5.33 removed; full reactor green (11:26 min); enforcer passes in all 13 root-pom modules; test counts identical to commit 3 |

**Step 1a status:** all commits done, full reactor green. Waiting for review → push `WI01124532-aws-sdk-upgrade-pom` and open the PR (title starting `WI01124532`) into `feature/WI01124532-aws-sdk-upgrade`.

**Acceptance criterion 5 (`dependency:tree`, after commit 4)** — services on the root pom:

| Library | Version | Modules |
|---|---|---|
| `jackson-databind` | 2.21.8 | shared, event-writer, dispatcher, splitter, transformer, distributor, distributor-rest, ingestor, error-processor, email-sender, watermill-publisher |
| `jetty-server` | 12.1.14 | same |
| `slf4j-api` | 2.0.18 | same + gen2-parser |
| `logback-core` | 1.5.38 | same + gen2-parser |
| `logback-classic` | 1.5.38 | all except watermill-publisher (1.5.33, fixed by commits 5–6) |

**Key build guard — root `maven-enforcer-plugin` execution `logback-pair`:** goal `enforce` (phase `validate`), rule `requireSameVersions` over `ch.qos.logback:logback-classic` and `ch.qos.logback:logback-core`. Runs for every child of the root pom, so a module that pins one half of the pair fails the build at `validate`, before compiling ([D5](../decisions.md#d5)).

**Green change details (`pom.xml`):**

- Properties: `mercury.commons.version` = `1.0.38-SNAPSHOT` (new); `jetty.version` 12.1.9 → 12.1.14; `jackson.bom.version` 2.21.4 → 2.21.8; `slf4j-api.version` 2.0.17 → 2.0.18; `logback-classic.version` 1.5.33 → 1.5.38.
- `dependencyManagement`: `logback-classic` + `logback-core` (one property, [D3](../decisions.md#d3)) and `slf4j-api`, placed before the Dropwizard BOM so they win; `com.inttra.mercury:commons`, `cloud-sdk-api`, `cloud-sdk-aws` at `${mercury.commons.version}` (managed only; `shared` starts depending on them in step 1b).
- `gen2-parser/pom.xml`: removed its local `slf4j-api.version` 2.0.17 / `logback-classic.version` 1.5.21 overrides, so it inherits the root pins.

**Not changed in 1a (and why):** Guava (root 33.1.0-jre, commons 33.5.0-jre) only downgrades commons once a module depends on commons, which starts in step 1b; covered by a red/green cycle there ([A17](../closed-items.md#a17)). Mockito (root 2.27.0, commons 5.10.0) is test scope and not transitive; revisit when new tests need `mockito-junit-jupiter` ([A18](../actions.md#a18)). functional-testing and watermill keep their own pins until steps 1e and 4.
