# Commons 1.0.39-SNAPSHOT: confirming the CI publish

← [How-to index](README.md) · [Tracker home](../README.md)


Approach: **don't trust the log alone, check the repository.** The log shows that Jenkins *ran* the deploy. The repository shows that the files *arrived*.

```text
 Jenkins log (4.7 MB)            Maven repository (inttra-maven)              Published jar
 ────────────────────            ───────────────────────────────              ─────────────
 1. right branch + commit?  ──►  3. maven-metadata.xml per module  ──►       4. download one jar,
 2. 6 deploy steps + SUCCESS?       HTTP 200, timestamp = log time              check U3/U8 methods exist
```

### Step 1 — Size up the log before reading it

```bash
f="/c/Users/arijit.kundu/OneDrive - WiseTech Global/Documents/platform/aws-upgrade/1.0.39-SNAPSHOT.log"
wc -lc "$f"
```

| Part | Meaning |
|---|---|
| `f="…"` | store the path in a variable. The **double quotes** keep the spaces in `OneDrive - WiseTech Global` together |
| `/c/Users/…` | Git Bash spelling of `C:\Users\…` |
| `wc -lc` | **w**ord **c**ount: `-l` lines, `-c` bytes |
| `"$f"` | always quote the variable when using it, or the spaces split it into several arguments |

Result: `45205` lines, `4779631` bytes. That's too big to read whole, so use searches.

### Step 2 — Pull out only the key lines

```bash
grep -nE "Uploaded to|Uploading to|BUILD (SUCCESS|FAILURE)|Finished:|Started by|Checking out Revision|Building .*1\.0\.|\[ERROR\]|deploy" "$f" | head -80
```

| Part | Meaning |
|---|---|
| `grep` | print lines that match a pattern |
| `-n` | prefix each match with its line number, so you can jump there with `sed` later |
| `-E` | **extended** regex: `\|`, `( )`, `+` work without backslashes |
| `A\|B\|C` | alternation: match any of the alternatives |
| `BUILD (SUCCESS\|FAILURE)` | group: either word after `BUILD ` |
| `Building .*1\.0\.` | `.*` = any characters. `\.` = a literal dot (a bare `.` means "any character") |
| `\[ERROR\]` | `[` `]` escaped, otherwise they would form a character class |
| `\| head -80` | pipe: show only the first 80 matching lines |

What it showed:

| Line(s) | Evidence |
|---|---|
| 1 | `Started by user Nishith N` |
| 96–116 | the build script: six `mvn -ntp deploy:deploy-file … -DrepositoryId=inttra-maven -Durl=https://inttra-ci.dev.e2open.com/maven2` |
| 513, 20979, 44400, 44650, 44894, 45171 | six `deploy:3.1.0:deploy-file` executions, each followed by `BUILD SUCCESS` |
| 45206 | `Finished: SUCCESS` |
| — | **no** `Uploaded to` lines at all. See the explanation below |

**Why there are no "Uploaded" lines:** `-ntp` (`--no-transfer-progress`) makes Maven print nothing about downloads or uploads. So the log *cannot* prove the upload, and that's why steps 4–5 check the repository.

### Step 3 — Read exact line ranges (commit, script, deploy blocks)

```bash
sed -n '1,30p' "$f" | cut -c1-250
grep -nE "git|Revision|branch|commit" "$f" | head -20 | cut -c1-250
sed -n '84,125p' "$f" | cut -c1-300
for r in 505,530 20975,20996 44396,44416 44646,44666 44890,44910 45167,45206; do sed -n "${r}p" "$f" | cut -c1-250; echo ====; done
```

| Part | Meaning |
|---|---|
| `sed -n '1,30p'` | **s**tream **ed**itor. `-n` = don't print every line by default. `1,30p` = **p**rint lines 1 to 30 |
| `cut -c1-250` | keep only characters 1–250 of each line, which tames very long log lines |
| `for r in A B C; do …; done` | loop: run the body once per value, with `$r` set to it |
| `"${r}p"` | `${r}` expands to e.g. `505,530`. The braces separate the variable from the `p` that follows. **Double** quotes are needed so `$r` expands (single quotes would keep it literal) |
| `echo ====` | print a separator between blocks |

Evidence: lines 23–29 show `branch: feature/ION-12310-commons-cloudsdk-refactoring, commit: aa52175716a51b8fb6727c5612eb2d8f5ef88a61, release: 1.0.39-SNAPSHOT`. The job's subject line is `Mercury_Commons_Publish`.

The deploy blocks show `mercury-services-commons 1.0 … SUCCESS` and the child modules `SKIPPED`. That's normal: `deploy-file` publishes one named file and runs once in the root project, so Maven marks the rest of the reactor as skipped.

### Step 4 — Scan for error words, then read what matched

```bash
grep -c "WARN.*deploy\|Failed to deploy\|401\|403" "$f"
grep -n  "WARN.*deploy\|Failed to deploy\|401\|403" "$f" | cut -c1-200 | head -20
```

| Part | Meaning |
|---|---|
| `-c` | **c**ount the matching lines instead of printing them |
| backslash + pipe (no `-E`) | without `-E` grep uses **basic** regex, where "or" is written as a backslash followed by a pipe, as in the command above |
| `WARN.*deploy` | `WARN`, anything, then `deploy` on the same line |
| `401`, `403` | HTTP "unauthorised" and "forbidden", the usual deploy failures |

The count was 18, but reading them showed **none** were deploy failures. They were timestamps such as `05:51:26.401`, a test-time `SnsException … 403` from a negative unit test, and `Time elapsed: 0.403 s`.

Lesson: **always read the matches behind a count.** Short numeric patterns like `401` match timestamps.

### Step 5 — Check the repository itself (the decisive check)

```bash
for a in cloud-sdk-api cloud-sdk-aws commons dynamo-client dynamo-integration-test email-sender; do
  echo "== $a"
  curl -s -m 15 -o - -w " [HTTP %{http_code}]\n" \
    "https://inttra-ci.dev.e2open.com/maven2/com/inttra/mercury/$a/1.0.39-SNAPSHOT/maven-metadata.xml" \
    | grep -E "lastUpdated|timestamp|buildNumber|HTTP"
done
```

A Maven repository is a set of static files with a fixed layout:

```text
https://inttra-ci.dev.e2open.com/maven2 / com/inttra/mercury / cloud-sdk-api / 1.0.39-SNAPSHOT / maven-metadata.xml
└──────────── repository URL ─────────┘ └── groupId, dots→/ ┘ └ artifactId ┘ └─── version ───┘ └ index of snapshot builds ┘
```

| Part | Meaning |
|---|---|
| `curl -s` | silent: no progress bar |
| `-m 15` | give up after 15 seconds (max time) |
| `-o -` | write the body to standard output (`-` = stdout) so it can be piped to `grep` |
| `-w " [HTTP %{http_code}]\n"` | after the body, also print the HTTP status code (`200` = found, `404` = missing) |
| `\` at line end | continue the command on the next line |
| `grep -E "lastUpdated\|timestamp\|…"` | keep only the interesting XML lines |

Result (all six modules):

| Module | HTTP | `timestamp` | `buildNumber` |
|---|---|---|---|
| cloud-sdk-api | 200 | `20261117.055030` | 1 |
| cloud-sdk-aws | 200 | `20261117.055227` | 1 |
| commons | 200 | `20261117.055359` | 1 |
| dynamo-integration-test | 200 | `20261117.055421` | 1 |
| dynamo-client | 200 | `20261117.055438` | 1 |
| email-sender | 200 | `20261117.055451` | 1 |

These timestamps (UTC) fall inside the job's run (deploys 05:50–05:54, `Finished at: 2026-11-17T05:54:51Z`). `buildNumber 1` means this is the first 1.0.39-SNAPSHOT upload, so nothing older exists to be confused with.

A snapshot's real file name is `<artifact>-<version without -SNAPSHOT>-<timestamp>-<buildNumber>.jar`, for example `cloud-sdk-api-1.0.39-20261117.055030-1.jar`.

### Step 6 — Prove the content: download one jar and look for the new methods

```bash
d=<scratchpad>/jarcheck; mkdir -p "$d"
curl -s -m 30 -o "$d/api.jar" \
  "https://inttra-ci.dev.e2open.com/maven2/com/inttra/mercury/cloud-sdk-api/1.0.39-SNAPSHOT/cloud-sdk-api-1.0.39-20261117.055030-1.jar"
unzip -l "$d/api.jar" | grep -iE "StorageClient|EmailService"
javap -cp "$d/api.jar" com.inttra.mercury.cloudsdk.storage.api.StorageClient | grep getObjectSize
javap -cp "$d/api.jar" com.inttra.mercury.cloudsdk.email.api.EmailService   | grep sendEmailWithResult
```

| Part | Meaning |
|---|---|
| `mkdir -p` | create the folder, and its parents, with no error if it already exists |
| `curl -o file` | save the download to a file |
| `unzip -l` | **l**ist the jar's entries (a jar is a zip) without extracting |
| `grep -i` | case-insensitive |
| `javap -cp <jar> <class>` | print the class's public method signatures straight from the jar, without unzipping |

Result:

```text
public default long getObjectSize(java.lang.String, java.lang.String);                      <- U3
public default ...EmailSendResult sendEmailWithResult(java.lang.String, java.util.List<...>, ...);  <- U8
```

The first attempt used `unzip -o -q … -d x` and `grep -rla getObjectSize x`. That works too: `-a` makes grep treat a binary `.class` file as text, `-r` recurses, and `-l` lists only file names. But `javap` gives a clearer answer.

### Step 7 — Dead ends worth knowing

| Tried | Result | Why it didn't help |
|---|---|---|
| Local `~/.m2/repository/com/inttra/mercury/cloud-sdk-aws/1.0.39-SNAPSHOT/` | `maven-metadata-local.xml` with `<localCopy>true</localCopy>`, `_remote.repositories` with `…jar>=` (no repo id) | Proves only **your** `mvn install` (2026-11-12), not the shared repository |
| JFrog CLI `jf rt s --server-id inttra-artifactory "*/com/inttra/mercury/cloud-sdk-api/1.0.39-SNAPSHOT/*.pom"` | `Found 0 artifacts`, **also for 1.0.38-SNAPSHOT**, which certainly exists | Search scope/permissions wrong. A check that fails on a known-good case proves nothing |
| Looking for `Uploaded to` in the Jenkins log | none | hidden by `-ntp` (Step 2) |

Lesson: test a check on a case you know is true (1.0.38) before you trust a negative result.
