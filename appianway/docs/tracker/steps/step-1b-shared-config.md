# Step 1b — commons config chain (`WI01124532-aws-sdk-upgrade-shared-config`)

← [Tracker home](../README.md) · [All steps](README.md)


Stacked on `WI01124532-aws-sdk-upgrade-pom` until PR #76 merges ([D6](../decisions.md#d6)).

**Plan (TDD cycles):**

| Cycle | Red | Green | Refactor |
|---|---|---|---|
| A | Tests + skeletons for `ConfigTransformChain`, `PropertiesSources`; `ConfigResolutionGoldenTest` | `shared` depends on `commons` (exclusions, [D7](../decisions.md#d7)); implement both classes | — |
| B | Root enforcer `requireUpperBoundDeps` for Guava and AWS SDK v1 (no-downgrade guard, [A17](../closed-items.md#a17)) | Raise `google-guava.version` and `aws-java-sdk.version` to the commons versions | — |
| C | Command test: `ConfigProcessingServerCommand` builds its source with the commons chain (comment lines removed, `${awsps:}` through the lookup) | Rewire the command onto `ConfigTransformChain` ([D8](../decisions.md#d8), [D9](../decisions.md#d9)) | Move the previous lookup classes (`config.lookup.*`) to test sources as the golden-test oracle |

**Key classes:**

| Class | Role | Important methods |
|---|---|---|
| `com.inttra.mercury.shared.config.ConfigTransformChain` (new) | Builds the commons chain `PropertiesSubstitutionConfigProvider → TrimConfigCommentsTransform → ParameterStoreConfigTransform` around a YAML source | `create(yamlSource, properties, environment, parameterStoreLookup)`: overlays `environment` on `properties` (env first, as today); wraps the Parameter Store lookup in `Suppliers.memoize` so the SSM client is only built on the first `${awsps:}` ([D9](../decisions.md#d9)) |
| `com.inttra.mercury.shared.config.PropertiesSources` (new) | Reads the `run` command's `.properties` paths through the bootstrap source provider (file system or S3) | `load(source, paths)`: each file read as UTF-8, joined with the line separator in command-line order, parsed once with `Properties.load(Reader)`, so later files override earlier keys exactly as the previous command did |
| `com.inttra.mercury.shared.command.ConfigProcessingServerCommand` (changed in cycle C) | Same CLI `run (yaml) (properties...)`, same constructors | `run(bootstrap, namespace)` |

**Tests:**

| Test class | Unit | Cases |
|---|---|---|
| `ConfigTransformChainTest` | `ConfigTransformChain` | properties placeholder; environment before properties (test-only env key, so the build machine's environment cannot interfere); `${k:-default}`; property referencing another property (`datadog.properties` uses `${componentName}`); unresolved placeholder fails naming the key; unresolved placeholder **on a comment line** still fails (same as today); comment lines removed; `${awsps:}` via the lookup; lookup not created without `${awsps:}`; lookup created once for several |
| `PropertiesSourcesTest` | `PropertiesSources` | UTF-8 (`Zürich`); later file overrides; last line without newline kept; no paths → empty; missing file → `IOException` naming the path |
| `ConfigResolutionGoldenTest` | Acceptance criterion 4 | **89 cases** = 16 services × their deployed environments × app variants (splitter `ce-`, transformer `ce-` / `os-`, ingestor `ce-`). Each case rebuilds the real start command from `run.sh` (`run <yaml> ./<app>.properties ./network-services.properties ./datadog.properties`): app properties from `<module>/conf/<env>/`, the others from `configuration/<env>/`, environment variables from the module's ECS task JSON. The previous shared resolver (`VariableLookupProvider` + `ProcessedConfigProvider`) is the oracle; output compared with comment lines removed; both must resolve identically or both fail. `local` environments are skipped (no `configuration/local`). Plus `everyModuleHasAtLeastOneCase` |

**Commits:**

| # | Commit | Type | Result |
|---|---|---|---|
| 1 | `8bf1db21` WI01124532 red: commons config chain must resolve configuration like the shared command | red | 85 golden cases + all 15 unit tests fail on the skeletons; 4 stress cases fail in both resolvers ([F6](../closed-items.md#f6)) |
| 2 | `9a704fb0` WI01124532 green: shared builds configuration with the commons chain classes | green | Golden 90/90; full reactor green (13:04 min); counts unchanged except `shared` +105 |
| 3 | `d21bb68e` WI01124532 red: no AppianWay pin may downgrade Guava or AWS SDK v1 below commons | red | Root enforcer execution `no-downgrade` (`requireUpperBoundDeps`, includes `com.google.guava:guava`, `com.amazonaws:aws-java-sdk-{core,s3,sqs,sns}`) fails `shared`: 1.12.720 pinned, `cloud-sdk-aws` needs 1.12.730 |
| 4 | `1294b884` WI01124532 green: raise Guava and AWS SDK v1 pins to the commons versions | green | `aws-java-sdk.version` 1.12.720 → 1.12.730; `google-guava.version` 33.1.0-jre → 33.6.0-jre (Dropwizard-managed; ≥ commons 33.5.0-jre). Enforcer passes everywhere; full reactor green in the build worktree (8:39 min, after [F7](../findings.md#f7)); counts unchanged ([A17](../closed-items.md#a17) done) |
| 5 | `98f28d96` WI01124532 red: ConfigProcessingServerCommand must build its source with the commons chain | red | `ConfigProcessingServerCommandSourceTest` 5/6 fail on stub hooks |
| 6 | `e23ec6cf` WI01124532 green: ConfigProcessingServerCommand resolves configuration with the commons chain | green | Command tests 6/6 + existing JUnit 4 20/20 + golden 90/90; full reactor green (7:42 min); counts unchanged except `shared` +6 |
| 7 | `0224e384` WI01124532 refactor: keep the previous config resolver only as the golden-test oracle | refactor | `config.lookup.*` (5 classes) moved `src/main` → `src/test` with `git mv` + `package-info` explaining the oracle role; full reactor green (7:38 min), counts unchanged |

**Step 1b status:** all commits done, full reactor green, local only. After #76 merges: rebase onto the feature branch ([D6](../decisions.md#d6)), re-run the full build, push, PR (title `WI01124532 shared: resolve configuration with the mercury-services-commons chain`).

**PR description:** `docs/redesign/pr-details/2026-10-31-apway-pr-1b-shared-config-description.md`.

**Cycle C details — `ConfigProcessingServerCommand`:**

| Method | Behaviour |
|---|---|
| `run(bootstrap, namespace)` | Unchanged CLI: reads the `properties` list, installs `createConfigurationSourceProvider(bootstrap.getConfigurationSourceProvider(), properties)`, then `super.run` |
| `createConfigurationSourceProvider(propertiesSource, propertiesPaths)` (new, `protected`) | `ConfigTransformChain.create(new ResourceConfigurationSourceProvider(), PropertiesSources.load(propertiesSource, paths), System.getenv(), this::createParameterStoreLookup)`. A read failure is logged (`Error reading config …`) and rethrown as `UncheckedIOException` — a `RuntimeException`, as the previous command threw (the existing JUnit 4 tests `testRunWithIOException…` assert this; [D11](../decisions.md#d11)) |
| `createParameterStoreLookup()` (new, `protected`) | `new com.inttra.mercury.config.ParameterStoreLookup()` (SSM, us-east-1, default credentials); called only on the first `${awsps:}` ([D9](../decisions.md#d9)) |
| Removed | private `createVarLookupProvider`, `streamToString` (the previous `config.lookup` path) |

Subclasses (`CreateMappingTemplate`, the three `DynamoTableCommand`s) only use the constructors, so they are unaffected.

**Dependency effect of cycle A (`dependency:tree`):** mysql-connector-java, MyBatis, POI, Jest 5.3.3, junit:junit (compile) absent; ingestor keeps Jest 6.3.1; bucket4j 8.7.0 and AWS SDK 2.x `sdk-core` 2.30.24 now present via commons. Gaps for cycle B: Guava — `shared` 33.6.0-jre (Dropwizard-managed) but dispatcher / ingestor 33.1.0-jre (module pin, below commons 33.5.0-jre); AWS SDK v1 — `shared` pins 1.12.720, `cloud-sdk-aws` expects 1.12.730.
