Step 1a of the WI01124532 AWS SDK upgrade: root pom only. No production code changes.

## Changes

1. **Tests run on the JUnit Platform** (`701cc85c`). The root pom no longer adds the `surefire-junit4` provider; every child gets `junit-jupiter` and `junit-vintage-engine` (test scope, versions from the Dropwizard junit-bom). Existing JUnit 4 tests run unchanged on the Vintage engine; new tests are JUnit 5.
   - Children inherit plugin dependencies, so transformer used to run its JUnit 5 tests on the JUnit 4 provider and skipped all of them. Transformer now runs **665 tests (5 skipped), all passing**, up from 4.
2. **Platform pins aligned with mercury-services-commons 1.0.38** (`42593970` red, `3f27f8e7` green). The old pins were lower than commons, and dependency management overrides transitive versions, so they would have downgraded commons' libraries.
   - Jetty 12.1.9 → 12.1.14, Jackson 2.21.4 → 2.21.8, logback 1.5.33 → 1.5.38, slf4j 2.0.17 → 2.0.18.
   - `logback-core` is now pinned with `logback-classic`.
   - `mercury.commons.version` = 1.0.38-SNAPSHOT; `commons`, `cloud-sdk-api` and `cloud-sdk-aws` are in dependency management. No module uses them yet.
   - gen2-parser's local slf4j and logback overrides are removed.
   - Guard: `shared` `PlatformLibraryVersionsTest` (JUnit 5 + AssertJ) reads the resolved versions from the jars' `pom.properties`.
3. **Tidy** (`9b0a1235`): stale version comments, a duplicate property and an unused property. No resolved version changes.
4. **One logback version per module** (`fb837d9d` red, `6bb9ae6c` green). A root `maven-enforcer-plugin` `requireSameVersions` rule fails any module whose `logback-classic` and `logback-core` differ. It caught watermill-publisher, which hardcoded `logback-classic` 1.5.33. That pin is removed, so it now uses the root version.

## Verification

- Full reactor `mvn clean verify`: green.
- Test counts per module, before → after:

| Module | Before | After |
|---|---|---|
| shared | 1510 | 1517 (+7 new) |
| transformer | 4 | 665 |
| every other module | unchanged | unchanged |

- `dependency:tree` for shared and all 11 root-pom services: `jackson-databind` 2.21.8, `jetty-server` 12.1.14, `slf4j-api` 2.0.18, `logback-classic` / `logback-core` 1.5.38.
- The enforcer `logback-pair` rule passes in all 13 root-pom modules.

## Not in this PR

- Guava 33.1.0-jre → 33.5.0-jre: comes in step 1b, when `shared` starts depending on commons.
- Mockito: test scope only; comes in step 1c.
- functional-testing and the watermill tree (which don't inherit the root pom) keep their own pins until steps 1e and 4.

Local builds also need `-Daether.enhancedLocalRepository.trackingFilename=_any.repositories`, because the cached `dynamo-client:1.0` for registration-inbound-consumers is otherwise refused. This happens on `develop` too.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
