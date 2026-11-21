# Running a service locally (Windows)

← [Index](README.md) · [How-to: build and run a service locally](../howto/build-and-run-a-service-locally.md)

`S` / `R` = the run folder in the session scratchpad (the jars, yaml, properties and the two scripts). Durable copies of the scripts: [runtime/fixtures/test6-transformer/](../runtime/fixtures/test6-transformer/). Credentials: [aws/basics.md](../runtime/aws/basics.md#7-credentials).

<a id="8-local-run-and-stop"></a>
## Starting and stopping with a real Ctrl+C (Windows)

```bash
cd $S; eval "$(aws configure export-credentials --profile $P --format env)"; export AWS_REGION=us-east-1 AWS_DEFAULT_REGION=us-east-1
java -Xmx384m -jar dispatcher-v2.jar run dispatcher.yaml dispatcher.properties network-services.properties datadog.properties > run-v2.log 2>&1
```
The normal start, run in the background. `run <yaml> <properties…>` is the Dropwizard command: the yaml from the jar, the properties files from the current folder (the QA ones with the borrowed queues and the local port). Stopping it with `taskkill /F` or `Stop-Process -Force` kills the JVM **without** its shutdown hooks: enough for the functional tests, not for a shutdown check.

```bash
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(cygpath -w $S/start-java.ps1)" -Jar dispatcher-v2.jar -Log run-burst > launcher.out 2>&1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(cygpath -w $S/send-ctrl-c.ps1)" -ProcessId <pid>
```
For the shutdown check (test 4b) the service must get a real **Ctrl+C**, which on Windows is what makes the JVM run its shutdown hooks (as SIGTERM does in ECS).
- `start-java.ps1` starts java in its **own console window** (`Start-Process`), so a Ctrl+C can be sent to that console alone, and writes the PID to `<Log>.pid`. It first calls `SetConsoleCtrlHandler(NULL, FALSE)`. A process started from the tool's shell inherits an "ignore Ctrl+C" flag, and java would inherit it too and ignore the Ctrl+C. That is what happened on the first attempt (15:32).
- `send-ctrl-c.ps1` leaves its own console (`FreeConsole`), joins java's (`AttachConsole <pid>`), ignores the event itself (`SetConsoleCtrlHandler(NULL, TRUE)`), and sends `GenerateConsoleCtrlEvent(0 = CTRL_C_EVENT, 0 = every process on that console)`.
- `-ExecutionPolicy Bypass` lets this one PowerShell run the local script file; it changes no setting.
- The exit is timed from PowerShell with `(Get-Process -Id <pid>).WaitForExit(90000)`, which waits until the process ends (at most 90 s). Check that the process is really gone with `Get-Process -Id <pid>` or `Get-NetTCPConnection -LocalPort 18084`. A `tasklist` check from Git Bash gave a wrong "gone" on the first attempt.
- In PowerShell, variable names ignore case: `$p` (a process) overwrites `$P` (the profile name). Use distinct names (`$prof`, `$proc`).

<a id="start-check-stop"></a>
## Start, wait, health check and stop with the generic script (transformer, test 6)

```bash
eval "$(aws configure export-credentials --profile $P --format env)"; export AWS_REGION=us-east-1 AWS_DEFAULT_REGION=us-east-1
cp transformer.yaml.v2 transformer.yaml
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(cygpath -w $R/start-java.ps1)" -Service transformer -Jar transformer-v2.jar \
  -Log boot-v2 -Xmx 1536m -JvmOpts "-Dcontivo.runtime.classpath=$(cygpath -w $R/maps);-Dcontivo.runtime.datadir=$(cygpath -w $R/data)"
```

- Credentials into this shell only ([aws-commands §7](../runtime/aws/basics.md#7-credentials)); the java process inherits them.
- `start-java.ps1` is now **generic** (tests 4 and 5 had splitter's names inside): `-Service` gives the yaml and properties names, `-Xmx` the heap, `-JvmOpts` extra JVM options. It runs `java -Xmx<n> <opts> -jar <jar> run <service>.yaml <service>.properties network-services.properties datadog.properties` in its own console (so Ctrl+C can be sent to it alone) and writes the PID to `<Log>.pid`.
- `-JvmOpts` takes the options **separated by `;`**. A value like `"a","b"` passed from Bash to `powershell -File` arrives as one string `a,b`: the first attempt gave java a single option `-Dcontivo.runtime.classpath=…maps,-Dcontivo.runtime.datadir=…`. The script now splits on `;`.
- `cygpath -w` turns a Git Bash path (`/c/Users/…`) into a Windows path (`C:\Users\…`), which java and PowerShell need.
- `-Dcontivo.runtime.classpath=<folder>` is where Contivo looks for map jars (`/app01/maps` on ECS); `-Dcontivo.runtime.datadir` is its work folder. `-Xmx1536m`: QA gives the container 3 GB; 1.5 GB is plenty for single documents.

```bash
for i in $(seq 1 90); do grep -q -E "Started @|Exception" boot-v2.log && break; sleep 1; done
curl -s -m 60 -o hc-v2.json -w "HTTP %{http_code} %{time_total}s\n" http://localhost:18086/admin/healthcheck
python -c "import json;d=json.load(open('hc-v2.json'));[print(k,v.get('healthy'),v.get('duration')) for k,v in d.items()]"
```

Waits up to 90 s for the start (`seq 1 90` counts 1…90; `grep -q` prints nothing and only sets the exit status, so `&& break` leaves the loop on the first match). Then reads Dropwizard's health check on the admin path (the yaml's `simple` server serves the application and `/admin` on one port, 18086), saves the JSON and prints each check's name, result and duration in ms (`python -c` runs a one-line program; `json.load` reads the file).

```bash
pid=$(tr -d '\r\n' < boot-v2.pid)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(cygpath -w $R/send-ctrl-c.ps1)" -ProcessId $pid
powershell.exe -NoProfile -Command "\$x=Get-Process -Id $pid -ErrorAction SilentlyContinue; if(\$x){[void]\$x.WaitForExit(60000)}; if(Get-Process -Id $pid -ErrorAction SilentlyContinue){'still running'}else{'exited'}"
grep -E "Closing|shut down|ERROR" boot-v2.log
```

`tr -d '\r\n'` removes the line end PowerShell wrote after the PID. `send-ctrl-c.ps1` sends a real Ctrl+C ([above](#8-local-run-and-stop)). The second PowerShell line waits up to 60 s for the process to end and says whether it is gone; inside Bash double quotes, `\$x` keeps `$x` for PowerShell, while Bash fills in `$pid`. The `grep` shows the clients closing.
