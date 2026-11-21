# Building in the build worktree

← [Index](README.md) · [How-to: build and run a service locally](../howto/build-and-run-a-service-locally.md)

The build worktree keeps the IDE away from Maven's `target/` folders ([G4](../rules.md#g4)). The walkthrough that uses these commands end to end: [howto/build-and-run-a-service-locally.md](../howto/build-and-run-a-service-locally.md).

<a id="s9-5"></a>
## The build worktree (G4)

```bash
git worktree add --detach ../appianway-build HEAD
git diff > /tmp/wip.patch && git -C ../appianway-build apply /tmp/wip.patch
cd ../appianway-build && mvn -B clean verify -Ddependency-check.skip=true -Daether.enhancedLocalRepository.trackingFilename=_any.repositories
```

`git worktree add` checks out a second working directory that shares the same repository (objects, branches) — no second clone. `--detach` checks out the commit itself rather than a branch (a branch can only be checked out in one worktree at a time, and the main tree already has it). `git diff > patch` captures uncommitted changes and `git -C <dir> apply` applies them in the other worktree (`-C` runs git as if started in `<dir>`). Building there keeps the IDE's automatic Java build from touching Maven's `target/` folders ([F7](../findings.md#f7)).

```bash
git -C ../appianway-build checkout --detach <commit> && git -C ../appianway-build reset --hard
git worktree remove ../appianway-build
```

Moves the build worktree to another commit (discarding the applied patch), or deletes it when the work is done. `git worktree list` shows all worktrees.

<a id="full-build"></a>
## The full reactor build before a PR

```bash
cd ../appianway-build && git checkout -q --detach d937538e
JAVA_TOOL_OPTIONS=-Duser.timezone=UTC mvn -B -o clean verify -Daether.enhancedLocalRepository.trackingFilename=_any.repositories > <scratchpad>/full-build.log 2>&1
grep -E "FAILURE \[|BUILD|Total time" <scratchpad>/full-build.log
```

The full reactor build before a PR, in the build worktree ([9.5](#s9-5)) at the exact commit that will be pushed. `> file 2>&1` sends normal output and errors to one log file (the build prints tens of thousands of lines); the `grep` shows the reactor summary lines: one `SUCCESS [time]` per module, any `FAILURE [`, the final `BUILD SUCCESS/FAILURE` and the total time. `-q` is not used here on purpose: the per-module summary is the evidence.

<a id="two-jars"></a>
## Building v1 and the new build of one service (runtime tests)

`R` = the run folder in the session scratchpad (test 6: `rt6/`).

```bash
W=../appianway-build
for pair in "v1 222d58be" "v2 d937538e"; do set -- $pair
  git -C $W checkout -q --detach $2 && git -C $W reset -q --hard
  (cd $W && mvn -B -q -pl transformer -am package -DskipTests -Daether.enhancedLocalRepository.trackingFilename=_any.repositories) > $R/build-$1.log 2>&1
  cp $W/transformer/target/transformer-1.0-shaded.jar $R/transformer-$1.jar
done
```

- `for pair in "v1 222d58be" "v2 d937538e"` loops over two quoted words; `set -- $pair` splits the current one into `$1` (label) and `$2` (commit).
- `git -C $W checkout -q --detach <commit>` moves the build worktree to that commit without a branch ([9.5](#s9-5), G4); `reset -q --hard` drops any leftover change in that worktree only; `-q` quiet.
- v1 = `222d58be`, the feature branch tip, where transformer is still on SDK v1; v2 = `d937538e`, the PR #9 head.
- `( cd $W && mvn … )`: the parentheses run it in a sub-shell, so the `cd` does not change the loop's folder. `-pl transformer -am` builds transformer **and the modules it needs** (`--also-make`: shared, schema-beans, structuralvalidator…), so the jar contains the code of that commit, not what happens to be in `~/.m2`. `package -DskipTests` compiles and builds the shaded jar without running tests (they ran in the PR build). `-B` batch mode, `-q` errors only. `> file 2>&1` sends standard output and errors to the log.
- Result: both exit 0, 201 MB each (mostly the Contivo engine). The shaded jar is `transformer-1.0-shaded.jar`.

```bash
unzip -l transformer-v2.jar | grep -o -E "shared/[a-z/]*(SQSListener|MessageQueueListener)\.class"
unzip -p transformer-v2.jar transformer.yaml > transformer.yaml.v2
```

`unzip -l` lists a jar's entries (a jar is a zip); `unzip -p` prints one entry to standard output: here the yaml packed in the jar, saved next to it so the local run uses exactly that build's yaml. `grep -o` prints only the matching part. Both jars contain both listeners (shared keeps the v1 one until step 5); the transformer code and the yaml differ (v2 has the cloud-sdk logger lines).
