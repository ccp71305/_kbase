# Maven commands

← [Index](README.md) · [Tracker home](../README.md)

Run from the repository root (or the build worktree, [build-worktree.md](build-worktree.md)) in Git Bash.

<a id="s9-4"></a>
## Builds

```bash
mvn -B clean verify -Ddependency-check.skip=true -Daether.enhancedLocalRepository.trackingFilename=_any.repositories
```

Full reactor build: `clean` deletes every `target/`; `verify` compiles, runs the unit tests (Surefire) and anything else bound up to the `verify` phase. `-B` (batch mode) gives plain, log-friendly output without download progress bars. `-Ddependency-check.skip=true` skips the OWASP dependency-check plugin (slow, network-heavy) during routine builds; run it separately when checking CVEs. `-Daether.enhancedLocalRepository.trackingFilename=_any.repositories` ([G2](../rules.md#g2)) points Maven's resolver at a tracking file that does not exist, so it stops checking which remote repository each cached artifact came from and accepts what is in `~/.m2` (needed locally for `dynamo-client:1.0`, [F1](../findings.md#f1)). Acceptance criterion 1: this must be green at every step.

```bash
mvn -B -pl shared -am verify
```

`-pl shared` (projects list) builds only the `shared` module; `-am` (also make) also builds the reactor modules it depends on. Fast loop for a single module.

```bash
mvn -B -pl shared,watermill-publisher verify -Ddependency-check.skip=true
```

Builds a service **together with `shared`** from source. A service built alone (`-pl watermill-publisher`) takes `mercury-shared:1.0` from `~/.m2`, which may be a stale jar left by another branch and gives misleading failures ([F4](../findings.md#f4)). `-pl a,b` lists several modules; Maven orders them by dependency.

```bash
mvn -B validate -fae
```

Runs only the `validate` phase (no compile, no tests) for the whole reactor; this is where the enforcer `logback-pair` rule runs, so it is the fastest way to check the logback pair in every module. `-fae` (fail at end) keeps going after a failing module, so one run lists every failing module instead of stopping at the first.

```bash
mvn -B -pl shared test -Dtest=PlatformLibraryVersionsTest
```

Runs a single test class. `-Dtest` accepts a class name, `Class#method`, or patterns such as `*VersionsTest`. Use it for the red/green loop.

```bash
mvn -B -pl dispatcher dependency:tree -Dincludes=org.eclipse.jetty,com.fasterxml.jackson.core,ch.qos.logback,org.slf4j
```

Prints the resolved dependency tree for one module. `-Dincludes=groupId[:artifactId]` (comma-separated) filters it to the libraries of interest. Acceptance criterion 5: every service resolves the commons-managed versions (no downgrade by AppianWay pins).

<a id="module-loop"></a>
## The module loop, installing `shared`, single tests

```bash
JAVA_TOOL_OPTIONS=-Duser.timezone=UTC mvn -B -o -pl transformer clean test -Daether.enhancedLocalRepository.trackingFilename=_any.repositories
```

The module loop used for every red/green pair. `JAVA_TOOL_OPTIONS=-Duser.timezone=UTC` (a Bash prefix: the variable is set for this one command only) is read by every JVM Maven starts, including the forked Surefire test JVM, so dates in events and `MetaData` are formatted in UTC as on CI; without it some time-formatting tests fail on a machine in another time zone. `-o` (offline) uses only `~/.m2`: no remote repository is contacted, which is faster and fails loudly if an artifact is missing instead of silently downloading another version. `-pl transformer` builds only that module and takes `shared` and `structuralvalidator` from `~/.m2`, so those must be installed first (next command). `clean test` deletes `target/` and runs compile + unit tests (stops before packaging). The `trackingFilename` flag is explained in [9.4](#s9-4).

```bash
JAVA_TOOL_OPTIONS=-Duser.timezone=UTC mvn -B -o -pl shared clean install -Daether.enhancedLocalRepository.trackingFilename=_any.repositories
JAVA_TOOL_OPTIONS=-Duser.timezone=UTC mvn -B -o -q -pl shared install -DskipTests
```

`install` runs everything up to `verify` and then copies the jar into `~/.m2/repository`, so another module built with `-pl` uses this version of `shared`. Run it after every `shared` change before testing transformer. `-DskipTests` compiles and installs without running the tests (used only right after the tests had passed in a separate run). `-q` (quiet) prints only warnings and errors: with `-q`, no output at all means success.

```bash
mvn -B -o -pl transformer test -Dtest='TransformerKnownDefects*,TransformerWireCompatibilityTest' -Dsurefire.failIfNoSpecifiedTests=false
```

Runs only the named test classes (comma-separated; `*` is a wildcard). The quotes stop Bash from expanding `*` against file names. `-Dsurefire.failIfNoSpecifiedTests=false` stops Surefire from failing when a pattern matches nothing in a module (needed when `-pl` lists several modules, or when a class name is mistyped and you want to see that rather than a build error).

```bash
mvn -B -o -q -pl transformer dependency:tree -Dincludes=com.amazonaws -DoutputFile=<scratchpad>/aws-tree.txt
grep -o "com.amazonaws:[^ ]*" <scratchpad>/aws-tree.txt | sort -u
```

Writes the resolved dependency tree, filtered to group `com.amazonaws`, to a file; `grep -o` + `sort -u` lists each SDK v1 artifact and version once. Used after removing the SDK v1 BOM to prove that only one SDK v1 version (1.12.730) remains in transformer's tree.

```bash
mvn -B -o -pl transformer test-compile
```

Compiles main and test code without running tests: the quickest way to list every test that breaks after a constructor or package change. If the output shows `BUILD FAILURE` from the enforcer instead of compiler errors, read the `RequireUpperBoundDeps` message (two versions of one jar met in the tree; that is how the SDK v1 BOM need was found).

<a id="s9-6"></a>
## Test-count check (acceptance criterion 7)

```bash
for d in $(find . -type d -name surefire-reports -path "*/target/*" | sort); do
  m=${d%/target/surefire-reports}
  t=$(grep -ho ' tests="[0-9]*"' $d/TEST-*.xml | grep -o '[0-9]*' | awk '{s+=$1} END {print s}')
  s=$(grep -ho ' skipped="[0-9]*"' $d/TEST-*.xml | grep -o '[0-9]*' | awk '{s+=$1} END {print s}')
  echo "$m $t $s"
done
```

After a full build, prints per module the total of the `tests="N"` and `skipped="N"` attributes of all its Surefire XML reports (`target/surefire-reports/TEST-*.xml`). `grep -ho` prints only the matching part without file names; the second `grep -o` keeps the number; `awk` adds the numbers up (`bc` is not installed in Git Bash). `${d%/target/surefire-reports}` strips that suffix to get the module path. Compare the output before and after a change: each module must show its previous count plus only the new tests, which proves no JUnit 4 test was silently skipped.
