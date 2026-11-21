# How-to: build v1 and the new build of a service, and run both locally against QA

← [How-to index](README.md) · [Runtime index](../runtime/README.md) · [Tracker home](../README.md)

Written 2026-11-20 from transformer's runtime test 6 ([log](../runtime/transformer.md#test-6)); the same steps were used for tests 1–5 with other service names. Every command is shown exactly as run, then explained part by part. Shell: **Git Bash** on Windows unless a block says PowerShell. Tool versions: Java 17.0.17 (Temurin), Maven 3.9.11, git 2.56, AWS CLI 2.34, Windows PowerShell 5.1 (`powershell.exe`).

**Standing rules** ([no ECS changes](../runtime-verification.md)): the app runs on this PC, never in ECS; it reads QA's real data, but every queue it would **write** to is replaced by that queue's DLQ ("borrowed"); objects are only added in the workspace bucket under marked roots `wi01124532-rt-*`; our messages are deleted at the end.

## Contents

1. [The idea: two builds, same inputs, compare](#1-idea)
2. [Variables used below](#2-variables)
3. [Build v1 and the new build](#3-build)
4. [Prepare the run folder](#4-prepare)
5. [Credentials](#5-credentials)
6. [Start, health check, send, stop](#6-run)
7. [Collect, compare, clean up](#7-collect)
8. [Pitfalls met so far](#8-pitfalls)

<a id="1-idea"></a>
## 1. The idea: two builds, same inputs, compare

```text
            build worktree (../appianway-build)
  git checkout 222d58be ──► mvn package ──► transformer-v1.jar   (feature tip: transformer still on SDK v1)
  git checkout d937538e ──► mvn package ──► transformer-v2.jar   (PR #9 head: transformer on cloud-sdk)

  run folder (scratchpad rt6/): jar + yaml + 3 properties files + maps/
     start v1 ─► send inputs (marked v1 roots) ─► Ctrl+C
     start v2 ─► send inputs (marked v2 roots) ─► Ctrl+C
     read what each sent / stored / published ─► compare v1 vs v2, and v2 vs QA's own run
```

**v1** is the code as it is in production today (the service still on AWS SDK v1); **v2** ("the new build") is the PR head. Both run the same way, one after the other, on port 18086, against the same borrowed queues. Each gets its own copies of the inputs, so its outputs and events land under its own root and can be compared side by side.

<a id="2-variables"></a>
## 2. Variables used below

```bash
P=642960533737_INTTRA2-QATeam                         # AWS CLI profile: QA account, QATeam SSO role
B=https://sqs.us-east-1.amazonaws.com/642960533737   # QA queue URL prefix
W=/c/Users/arijit.kundu/projects/appianway-build     # the build worktree
R=<scratchpad>/rt6                                    # the run folder (this session's scratchpad)
log(){ echo "$(date +%H:%M:%S) $*" >> $R/steps.log; } # timestamped step log
```

- `NAME=value` (no spaces around `=`) sets a shell variable; `$NAME` or `${NAME}` uses it. Variables live only in that one command's shell: the tool starts a new shell per command, so every block sets them again.
- `log(){ …; }` defines a small Bash function; `$*` is all its arguments; `>>` appends to the file (`>` would overwrite). `date +%H:%M:%S` prints the local time. Every step of a test is logged this way; the step log is copied into the fixtures afterwards ([test 6's](../runtime/fixtures/test6-transformer/steps.log)).

<a id="3-build"></a>
## 3. Build v1 and the new build

### 3.1 Why a separate worktree

The main checkout `appianway/` is open in VS Code, whose Java extension compiles into the same `target/` folders Maven uses; a Maven build there can pick up half-compiled classes ([F7](../findings.md#f7)). So builds run in a **second worktree** of the same repository ([G4](../rules.md#g4)), created once:

```bash
git worktree add --detach ../appianway-build HEAD
```

`git worktree add <path> <commit>` checks out another working folder that shares the repository's objects and branches (no second clone). `--detach` checks out the commit itself, not a branch: a branch can be checked out in only one worktree at a time. `git worktree list` shows both.

### 3.2 Check it is clean, then build each commit

```bash
git -C $W status --short          # must print nothing
git -C $W log -1 --oneline        # which commit it is on now
```

`-C <dir>` runs git as if started in `<dir>`. `status --short` prints one line per changed file: empty output = clean.

```bash
for pair in "v1 222d58be" "v2 d937538e"; do set -- $pair
  git -C $W checkout -q --detach $2 && git -C $W reset -q --hard
  (cd $W && mvn -B -q -pl transformer -am package -DskipTests -Daether.enhancedLocalRepository.trackingFilename=_any.repositories) > $R/build-$1.log 2>&1; rc=$?
  cp $W/transformer/target/transformer-1.0-shaded.jar $R/transformer-$1.jar
  log "build $1 ($2) exit $rc $(stat -c %s $R/transformer-$1.jar)"
done
```

Line by line:

| Part | Meaning |
|---|---|
| `for pair in "v1 222d58be" "v2 d937538e"; do … done` | Two loop rounds; the quotes keep label and commit together in one word |
| `set -- $pair` | Splits the word on the space into the positional parameters: `$1` = `v1`, `$2` = `222d58be` |
| `git -C $W checkout -q --detach $2` | Moves the build worktree to that commit (`-q` quiet) |
| `&& git -C $W reset -q --hard` | Only if the checkout worked (`&&`): throws away any change left in that worktree. Never run in the main checkout |
| `( cd $W && mvn … )` | Parentheses = a sub-shell: the `cd` does not leak into the loop |
| `mvn -B` | Batch mode: no colours or progress animation (clean logs) |
| `-q` | Quiet: only errors are printed |
| `-pl transformer` | "Project list": build the `transformer` module of the reactor |
| `-am` | "Also make": also build every module transformer depends on (`shared`, `schema-beans`, `structuralvalidator`, …) **from this commit**, instead of taking possibly older ones from `~/.m2` |
| `package` | Run the lifecycle up to `package`: compile, then build the jar; the shade plugin makes the runnable fat jar `transformer-1.0-shaded.jar` |
| `-DskipTests` | Compile the tests but do not run them (they ran in the PR's full build) |
| `-Daether…trackingFilename=_any.repositories` | Lets Maven reuse artifacts in `~/.m2` whichever repository they came from (explained in [commands: Maven builds](../commands/maven.md#s9-4)) |
| `> $R/build-$1.log 2>&1` | Standard output to the log file; `2>&1` sends errors to the same place |
| `rc=$?` | `$?` is the exit code of the last command (0 = success) |
| `cp … transformer-$1.jar` | Keeps each jar under its own name; the next round's build overwrites `target/` |
| `stat -c %s <file>` | The file size in bytes, for the log |

Result 2026-11-20: both exit 0, about 2 minutes each, 201 MB each (mostly the Contivo engine).

**Which commits:** v1 is the last commit where the service is still on SDK v1. For transformer that is the feature branch tip `222d58be` (transformer untouched there). v2 is the PR head. Find them with `git log --oneline -3 feature/WI01124532-aws-sdk-upgrade` and `gh pr view 9 --json headRefOid`.

### 3.3 Check the two jars are really different

```bash
unzip -p $R/transformer-v1.jar transformer.yaml > $R/transformer.yaml.v1
unzip -p $R/transformer-v2.jar transformer.yaml > $R/transformer.yaml.v2
diff $R/transformer.yaml.v1 $R/transformer.yaml.v2
```

A jar is a zip file. `unzip -p <zip> <entry>` prints one entry to standard output (`-l` would list all entries). The yaml packed in each jar is saved next to it, because each build must run with **its own** yaml (v2 adds the cloud-sdk logger lines). `diff` shows the lines that differ.

### 3.4 Back to the PR head

```bash
git -C $W checkout -q --detach d937538e && git -C $W status --short
```

The loop ends with the worktree on the last commit built (here already the PR head); `status` confirms it is clean.

<a id="4-prepare"></a>
## 4. Prepare the run folder

Everything the process reads is in `rt6/`:

| File | What | Where it comes from |
|---|---|---|
| `transformer-v1.jar`, `transformer-v2.jar` | The two builds | §3 |
| `transformer.yaml.v1`, `.v2` → copied to `transformer.yaml` before each start | Dropwizard configuration with `${…}` placeholders | §3.3 |
| `transformer.properties` | The values for the placeholders | QA's `transformer/conf/qa/transformer.properties`, every queue replaced by its `_dlq`, port 18086 ([copy](../runtime/fixtures/test6-transformer/transformer.local.properties)) |
| `network-services.properties` | Network Services URLs and client id/secret | QA's `configuration/qa/network-services.properties`, the two credentials read from SSM ([AWS commands: SSM](../runtime/aws/ssm-ses.md#5b-ssm)). **Scratchpad only, never in the tracker** |
| `datadog.properties` | Metrics tags | QA's `configuration/qa/datadog.properties`, unchanged |
| `maps/` | Contivo map jars | `mercury-services/booking/maps/lib/*.jar` (29) + `appianway/transformer/lib/maps/*.jar` (4 FA maps), identical to mercury-services `origin/develop` |
| `data/` | Contivo's work folder | empty folder |
| `start-java.ps1`, `send-ctrl-c.ps1` | Start in an own console; send Ctrl+C | [fixtures](../runtime/fixtures/test6-transformer/) |

```bash
mkdir -p $R/maps $R/data
cp /c/Users/arijit.kundu/projects/mercury-services/booking/maps/lib/*.jar $R/maps/
cp /c/Users/arijit.kundu/projects/appianway/transformer/lib/maps/*.jar $R/maps/
```

`mkdir -p` creates the folders and does not complain if they exist. `*.jar` is expanded by the shell to every jar in that folder.

**How the properties reach the yaml:** the service is started as `java -jar <jar> run transformer.yaml transformer.properties network-services.properties datadog.properties`. `run` is Dropwizard's server command; the AppianWay application class loads the listed properties files and substitutes every `${name}` / `${name:-default}` in the yaml with them before Dropwizard parses it. So a value is changed for the local run by changing the properties file only.

The edit that turned QA's properties into the local ones (example):

```bash
sed -i -E 's/^transformer.dynamoDbSequenceTable=.*/transformer.dynamoDbSequenceTable=inttra2_qa_controlnumber_sequence/' transformer.properties
```

`sed -i` edits the file in place; `-E` extended regular expressions; `s/<regex>/<replacement>/` replaces; `^` = start of line, `.*` = the rest of the line.

<a id="5-credentials"></a>
## 5. Credentials

```bash
aws sts get-caller-identity --profile $P
eval "$(aws configure export-credentials --profile $P --format env)"
export AWS_REGION=us-east-1 AWS_DEFAULT_REGION=us-east-1
```

- `sts get-caller-identity` proves the SSO login is still valid (it prints the account and role). If it has expired: `aws sso login --profile $P` opens the browser.
- `aws configure export-credentials --format env` prints the SSO session's temporary keys as `export AWS_ACCESS_KEY_ID=…` lines. `$( … )` captures that output; `eval` runs it in **this** shell. The keys are never printed or written to a file.
- `export` makes the variables visible to programs started from this shell: the java process inherits them. SDK v1 and SDK 2.x both read `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_SESSION_TOKEN` and the region variables first, so both builds use the same identity.

<a id="6-run"></a>
## 6. Start, health check, send, stop

### 6.1 Start

```bash
cd $R
cp transformer.yaml.v1 transformer.yaml
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(cygpath -w $R/start-java.ps1)" \
  -Service transformer -Jar transformer-v1.jar -Log run-v1 -Xmx 1536m \
  -JvmOpts "-Dcontivo.runtime.classpath=$(cygpath -w $R/maps);-Dcontivo.runtime.datadir=$(cygpath -w $R/data)" \
  > launcher-v1.out 2>&1
```

| Part | Meaning |
|---|---|
| `powershell.exe -NoProfile` | Windows PowerShell 5.1, without loading the user's profile script (faster, predictable) |
| `-ExecutionPolicy Bypass` | Allows this one run to execute a local `.ps1` file; changes no machine setting |
| `-File <script> -Service … -Jar …` | Runs the script; the following `-Name value` pairs are the script's `param(...)` |
| `cygpath -w <path>` | Converts a Git Bash path `/c/Users/…` to a Windows path `C:\Users\…` (java and PowerShell need those) |
| `-Xmx 1536m` | Java's maximum heap (1.5 GB; QA's container has 3 GB) |
| `-JvmOpts "a;b"` | Extra JVM options, **separated by `;`** (see pitfalls) |
| `-Dcontivo.runtime.classpath=<maps>` | Java system property read by Contivo: where to find the map jars (on ECS `/app01/maps`, from `run.sh`) |
| `-Dcontivo.runtime.datadir=<data>` | Contivo's work folder |
| `> launcher-v1.out 2>&1` | The launcher's own message to a file. **Do not pipe it into another program** (see pitfalls) |

What the script does ([source](../runtime/fixtures/test6-transformer/start-java.ps1)):

```powershell
[void][CtrlFlag]::SetConsoleCtrlHandler([IntPtr]::Zero, $false)
$JvmOpts = @($JvmOpts | ForEach-Object { $_ -split ';' } | Where-Object { $_ })
$javaArgs = @("-Xmx$Xmx") + $JvmOpts + @('-jar', $Jar, 'run', "$Service.yaml", "$Service.properties",
                                        'network-services.properties', 'datadog.properties')
$proc = Start-Process -FilePath java.exe -PassThru -WindowStyle Minimized -ArgumentList $javaArgs `
    -RedirectStandardOutput "$Log.log" -RedirectStandardError "$Log.err"
$proc.Id | Out-File -Encoding ascii "$Log.pid"
```

- `SetConsoleCtrlHandler(NULL, FALSE)` (a Windows API call, declared with `Add-Type` at the top): a process started from the tool's shell inherits the flag "ignore Ctrl+C", and java would inherit it too and never run its shutdown hooks. This clears it before java is created.
- `-split ';'` splits each option string on `;`; `Where-Object { $_ }` drops empty pieces; `@( … )` makes sure the result is an array.
- `Start-Process … -PassThru` starts java in a **new console window** (minimized) and returns the process object; that own console is what lets a Ctrl+C reach java alone later. `-RedirectStandardOutput/-Error` write java's output to `run-v1.log` / `run-v1.err`. The backtick `` ` `` at a line end continues the command on the next line (PowerShell's `\`).
- The PID goes to `run-v1.pid`, for the health check and the stop.

So the command java runs is:

```text
java -Xmx1536m -Dcontivo.runtime.classpath=C:\…\rt6\maps -Dcontivo.runtime.datadir=C:\…\rt6\data
     -jar transformer-v1.jar run transformer.yaml transformer.properties network-services.properties datadog.properties
```

### 6.2 Wait until it is up

```bash
for i in $(seq 1 90); do grep -q -E "SQSListener starting|MessageQueueListener starting|Exception in thread" run-v1.log 2>/dev/null && break; sleep 1; done
grep -m1 "starting" run-v1.log
```

`seq 1 90` prints 1…90, so the loop tries at most 90 times, one second apart. `grep -q` prints nothing and only sets the exit status; `&& break` leaves the loop at the first match. The pattern includes a failure (`Exception in thread`), so a crashed start does not look like "still starting". `2>/dev/null` hides "no such file" before the log exists. `grep -m1` stops after the first match. v1's listener is `SQSListener`, the new build's `MessageQueueListener`.

### 6.3 Health check

```bash
curl -s -m 60 -o hc-run-v1.json -w "health HTTP %{http_code} %{time_total}s\n" http://localhost:18086/admin/healthcheck
python -c "import json;d=json.load(open('hc-run-v1.json'));[print(k,v.get('healthy'),v.get('duration')) for k,v in d.items()]"
```

`curl -s` (silent) `-m 60` (give up after 60 s) `-o file` (save the body) `-w "…"` (print the HTTP status and the total time afterwards). The yaml's `server.type: simple` serves the application and the admin pages on one port; `/admin/healthcheck` runs every registered check and answers 200 if all are healthy. The one-line Python prints each check's name, result and duration (ms).

### 6.4 Send the inputs (WRITE, to the borrowed pickup DLQ)

```bash
for f in input-v1-*.json; do
  id=$(aws sqs send-message --profile $P --region us-east-1 --queue-url $B/inttra2_qa_sqs_transformer_inbound_dlq \
         --message-body "file://$(cygpath -w $R/$f)" --query MessageId --output text)
  echo "$f $id"; log "WRITE send $f -> transformer_inbound_dlq $id"
done
```

`--message-body file://<path>` makes the CLI read the body from the file (a JSON `MetaData`, the same message the upstream service would send). `--query MessageId --output text` prints only the new message's id. The service, polling that DLQ as its pickup queue, receives it within a second.

How the inputs were made: [make-inputs.py](../runtime/fixtures/test6-transformer/make-inputs.py) takes the upstream service's real message, points `rootWorkflowId`/`parentWorkflowId`/`fileName` at a marked copy of the object (`wi01124532-rt-tf-<build>-<case>/…`, made with `aws s3api copy-object`, [AWS commands: S3](../runtime/aws/s3.md#copy-object)) and gives it new `messageId`/`workflowId` values.

### 6.5 Watch it work

```bash
grep -E "Processing workflowId|Transformer name|Metadata successfully sent|ERROR|WARN|Exception|not found" run-v1.log \
  | sed -E 's/FormatConfigs : \{[^}]*\}//; s/^(\S+) +\[[0-9-]+ ([0-9:,]+)\] \[[^]]+\] +\S+ +: +/\1 \2 /' | cut -c1-200
```

`grep -E "a|b|…"` keeps the interesting lines (the pattern again includes failures). `sed -E` with two `s///` commands separated by `;`: the first removes the long `FormatConfigs : {…}` part (`\{` a literal brace, `[^}]*` anything up to the closing one); the second shortens the log prefix to "level time" using capture groups (`\S+` non-spaces, `\1` `\2` the captured parts). `cut -c1-200` keeps the first 200 characters per line.

### 6.6 Stop with Ctrl+C

```bash
pid=$(tr -d '\r\n' < run-v1.pid)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(cygpath -w $R/send-ctrl-c.ps1)" -ProcessId $pid
powershell.exe -NoProfile -Command "\$x=Get-Process -Id $pid -ErrorAction SilentlyContinue; if(\$x){[void]\$x.WaitForExit(60000)}; if(Get-Process -Id $pid -ErrorAction SilentlyContinue){'still running'}else{'exited'}"
grep -E "Closing|shut down" run-v1.log
```

- `tr -d '\r\n' < file` reads the PID file and deletes the line end PowerShell wrote (Windows `\r\n`).
- `send-ctrl-c.ps1` ([source](../runtime/fixtures/test6-transformer/send-ctrl-c.ps1)) leaves its own console (`FreeConsole`), joins java's (`AttachConsole <pid>`), makes itself ignore the event, and sends `CTRL_C_EVENT` to that console. Java then runs its shutdown hooks, as with SIGTERM when ECS stops a task. `taskkill /F` or `Stop-Process -Force` would kill java **without** them.
- The second line waits up to 60 s for the process to end. Inside Bash double quotes, `\$x` passes a literal `$x` to PowerShell, while `$pid` is filled in by Bash.
- The new build logs one "Closing … on application shutdown" line per cloud-sdk client.

Then the same §6.1–6.6 for v2 (`transformer.yaml.v2`, `transformer-v2.jar`, `-Log run-v2`, `input-v2-*.json`).

<a id="7-collect"></a>
## 7. Collect, compare, clean up

| Step | Script | What it does |
|---|---|---|
| Collect (read) | [collect.sh](../runtime/fixtures/test6-transformer/collect.sh) | `sqs receive-message --visibility-timeout 30` on each output DLQ (hides each message 30 s, deletes nothing), saves every body; `s3api get-object` of each object a message names, with its headers; `s3 cp --recursive` of the events stored under our roots (`eventstore/<UTC date>/<root>/`) |
| Compare v1 / v2 | [compare.py](../runtime/fixtures/test6-transformer/compare.py) | Pairs messages by queue, case, context, target; normalizes ids, roots and times; compares `MetaData`, document bytes (for differing documents, also with digits masked), headers, events |
| Compare v2 / QA | inline in the [test log](../runtime/transformer.md#test-6), pairs in [qa-pairs.tsv](../runtime/fixtures/test6-transformer/qa-pairs.tsv) | QA's own output objects of the same files, found as the next service's input in QA's events |
| Clean up (WRITE) | [cleanup.sh](../runtime/fixtures/test6-transformer/cleanup.sh) | Receives each DLQ's messages; deletes only those with `"component":"transformer"` and a `wi01124532-rt-tf-` root; any other message is made visible again at once (`change-message-visibility --visibility-timeout 0`) |

Afterwards every borrowed queue is checked empty with `get-queue-attributes` ([AWS commands: SQS](../runtime/aws/sqs.md#dlq-precheck)). The marked objects stay in the workspace (agreed).

<a id="8-pitfalls"></a>
## 8. Pitfalls met so far

| Pitfall | What happened | Fix |
|---|---|---|
| Piping the launcher (`powershell … \| cut`) | Bash waited for ever: java inherited the pipe's handle, so the pipe never closed (2026-11-20, 5-minute hang, nothing sent) | Redirect to a file (`> launcher.out 2>&1`) |
| `-JvmOpts "a","b"` from Bash | `powershell -File` received one string `a,b`: java got one option `-D…maps,-D…data` | The script splits on `;`; pass `"a;b"` |
| Windows line ends from Python | `keys.txt` had `\r\n`; each S3 key ended in an invisible `\r` and every `get-object` said NoSuchKey | `tr -d '\r'` before reading, or write files with `newline="\n"` |
| A wrong log window | Searching QA's log on the wrong day returns nothing, without an error (`MetaData` times and log times are UTC) | Take the window from the event's UTC `timestamp` |
| SQS counts lag | `ApproximateNumberOfMessages` showed 0 right after the sends, 3 twenty seconds later | Wait ~20 s before counting |
| Ignored Ctrl+C | A java started directly from the tool shell ignored Ctrl+C and never ran its hooks (test 4, 15:32) | `start-java.ps1` clears the inherited flag |
| `$p` vs `$P` in PowerShell | Variable names ignore case: a process `$p` overwrote the profile `$P` | Distinct names (`$proc`, `$prof`) |
| Missing map | Contivo fails with "The map '…' is not found" | Map names come from the integration profile format; read them from QA's log ("Transformer name : …"), jars from mercury-services `booking/maps/lib/` |
