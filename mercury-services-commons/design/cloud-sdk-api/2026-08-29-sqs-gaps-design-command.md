# SQS/SNS cloud-sdk gaps — command log and investigation record

**Companion to [2026-08-29-sqs-gaps-design.md](./2026-08-29-sqs-gaps-design.md).**

This document holds the three command logs that were originally inline in the design document. They
were split out because the design had grown past comfortable reading length; the design itself is
unchanged and remains the authoritative document. **Nothing here proposes a design decision** — this
is the evidence trail behind the decisions made there.

Section numbers deliberately **mirror the parent document**, so a reference to §14, §15.7 or §16.11
in the design resolves to the identically-numbered section here.

| Section | What it records | Supports |
| --- | --- | --- |
| [§14](#14-investigation-log) | How the gaps and the exception model were established — the reading of `MessagingClient`, the `javap` check against the resolved artifact, the SNS surface, the exception-hierarchy walk. Includes §14.1 *What was not done*. | §1–§13 |
| [§15.7](#157-verification-commands-for-this-appendix) | Reading AWS SDK v2's own retry defaults out of `sdk-core-2.30.24.jar`. | §15 |
| [§16.11](#1611-command-log--how-the-footprint-was-established) | The full `mercury-services` impact sweep, steps A–I. Each command in `git grep` form with the `rg` / `find` / `awk` / `sed` equivalent and its syntax explained. Step I is the verification that produced the §16.8 retraction. | §16 |

Every command was run in **Git Bash (POSIX `sh`) on Windows** from the relevant repository root, and
is reproducible as written.

---

## 14. Investigation log

Commands run to establish the facts in **§1–§13 of the design document**, with syntax
explained.

**Step 1 — confirm the current published surface of `MessagingClient`.**

```bash
sed -n '1,200p' cloud-sdk-api/src/main/java/com/inttra/mercury/cloudsdk/messaging/api/MessagingClient.java
```

Establishes that there is no delay-bearing method and that `changeMessageVisibility` is already a
`default` — the precedent reused in §4.3.

**Step 2 — confirm the abstraction gap is real in the *resolved artifact*, not just the working tree.**

```bash
javap -p -c -cp ~/.m2/repository/com/inttra/mercury/cloud-sdk-api/1.0.32-SNAPSHOT/cloud-sdk-api-1.0.32-SNAPSHOT.jar \
  com.inttra.mercury.cloudsdk.messaging.api.MessagingClient
```

`javap` disassembles a compiled class; `-p` includes private members, `-c` prints bytecode, `-cp`
points at the jar. This matters because the `mercury-services-commons` working tree can be *ahead*
of the artifact the consumer actually resolves — reading source alone would risk concluding a method
exists when the consumer's build cannot see it. This is how `changeMessageVisibility` was confirmed
present and `DelaySeconds` confirmed absent.

**Step 3 — read the builder precedent.**

```bash
cat cloud-sdk-api/src/main/java/com/inttra/mercury/cloudsdk/messaging/model/ReceiveMessageOptions.java
```

Source of the private-constructor / `@Getter` / null-tolerant-setter / unmodifiable-collection
pattern replicated verbatim in §4.2.

**Step 4 — locate every exception type in the API module.**

```bash
find cloud-sdk-api/src/main/java -name "*Exception*.java" | sed 's|.*/java/||'
```

`find -name` matches on filename with glob semantics; the `sed` strips the source-root prefix so the
output reads as package paths. Result: six classes, all `extends RuntimeException`, **no common
base** — the finding behind E2 and §8.1.

**Step 5 — confirm the SNS defect.**

```bash
cat cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/notification/exception/SnsExceptionHandler.java
grep -n "catch (SnsException" cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/notification/impl/SnsService.java
```

`grep -n` prints line numbers. Six hits (86, 113, 139, 161, 183, 205) — every one narrow enough to
let `SdkClientException` through, because `SdkClientException` branches off `SdkException`
*alongside* `SdkServiceException` rather than beneath it. This is E4.

**Step 6 — verify the AWS SDK v2 retryability API rather than assuming it.**

First establish *which* version to verify against. The local `~/.m2` held ten `sdk-core` versions
(2.16.46 … 2.42.28) pulled in by unrelated projects, so "newest jar present" is **not** the version
this module compiles against:

```bash
grep -rn -B2 -A3 "software.amazon.awssdk" --include=pom.xml . | grep -E "artifactId>bom|<version>2\."
```

`--include=pom.xml` restricts the recursive grep to POMs; `-B2 -A3` prints two lines before and
three after each hit so the `<artifactId>bom</artifactId>` and its `<version>` land in the same
window. Result: `cloud-sdk-aws/pom.xml:26` → **`2.30.24`** (and the same in
`dynamo-integration-test`). The root `pom.xml` property `aws.java.sdk.version = 1.12.730` is the
*v1* SDK and is unrelated.

Then disassemble that exact version:

```bash
cd /tmp && mkdir sdk3024 && cd sdk3024
unzip -o -q ~/.m2/repository/software/amazon/awssdk/sdk-core/2.30.24/sdk-core-2.30.24.jar \
      "software/amazon/awssdk/core/exception/*"
unzip -o -q ~/.m2/repository/software/amazon/awssdk/aws-core/2.30.24/aws-core-2.30.24.jar \
      "software/amazon/awssdk/awscore/exception/*"
javap -p software/amazon/awssdk/core/exception/SdkException.class        | grep -E "class|retryable"
javap -p software/amazon/awssdk/core/exception/SdkServiceException.class | grep -E "class|isRetryable|isThrottl|isClockSkew|statusCode"
javap -p software/amazon/awssdk/core/exception/SdkClientException.class  | grep -E "^public class"
javap -p software/amazon/awssdk/awscore/exception/AwsServiceException.class | grep -E "class|awsErrorDetails|isThrottl|isClockSkew"
```

Syntax: `unzip -o -q <jar> <member-glob>` extracts only matching members (`-o` overwrite, `-q`
quiet); `javap -p` disassembles a class including private members; `grep -E` is extended regex.

This confirmed at **2.30.24** every predicate used by `AwsFailureClassifier` (§8.3), the
`SdkClientException extends SdkException` branch that makes the ordering in §8.3 necessary, and the
`AwsServiceException` overrides of `isThrottlingException()` / `isClockSkewException()` that make a
separate `AwsServiceException` arm redundant. Every predicate in that classifier was read off
disassembled bytecode at the pinned version, not recalled and not extrapolated from a newer jar.

> **Correction.** An earlier revision of this document cited `2.42.28`, because the first pass
> selected the jar with `sort | tail -1` — the highest version in the local repository rather than
> the one the BOM pins. The API surface happens to be identical across both, so no conclusion
> changed, but the citation was wrong and the selection method was unsound. Verify against the
> pinned version, never against whatever `~/.m2` happens to hold.

**Step 7 — confirm the version property to bump.**

```bash
grep -n "dependency.version" pom.xml
```

Root `pom.xml` line 20: `<dependency.version>1.0.32-SNAPSHOT</dependency.version>` — the single
property driving the release version, per §10 step 1.

**Step 8 — confirm the consumer's pin.**

```bash
grep -n "mercury.commons.version" ../mft-s3-aqua-appia/pom.xml
```

`<mercury.commons.version>1.0.32-SNAPSHOT</mercury.commons.version>` — confirms the consumer is on
the current release and that §10 step 6 is a one-line bump.

**Step 9 — confirm package coordinates for every type referenced in this design.**

```bash
for f in <the five files>; do printf "%-60s " "$(basename $f)"; grep -m1 "^package" "$f"; done
```

`printf "%-60s"` left-pads to a fixed width so the output aligns; `grep -m1` stops after the first
match. Confirms `...messaging.api`, `...messaging.model`, `...messaging.exception`,
`...notification.exception`, `...notification.api` — so the new
`com.inttra.mercury.cloudsdk.exception` package in §8.1 sits alongside the existing convention
rather than cutting across it.

**Step 10 — check what can actually reach the classifier's fall-through arms (review challenge).**

A reviewer questioned the draft's
`if (t instanceof IOException || t instanceof InterruptedException) return true;` arm. Rather than
defend it, establish what can reach it.

```bash
# what does SqsMessagingClient actually call on the converter, and does the contract declare throws?
grep -nE "onverter|toString\(|Function<|serializ" \
     cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/messaging/aws/impl/SqsMessagingClient.java
sed -n '393,402p' cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/messaging/aws/impl/SqsMessagingClient.java
```

Result: `MessageConverter<T>` is a nested interface (line 395) declaring `String toString(T value)`
and `T fromString(String value)` — **neither declares `throws`**, so no checked exception can escape
a converter. That kills the `InterruptedException` case outright.

```bash
JC=$(find ~/.m2/repository/com/fasterxml/jackson/core/jackson-core -name "jackson-core-2.*.jar" \
     ! -name "*sources*" | sort -V | tail -1)
unzip -o -q "$JC" "com/fasterxml/jackson/core/JsonProcessingException.class" \
                  "com/fasterxml/jackson/core/JacksonException.class"
javap -p com/fasterxml/jackson/core/JsonProcessingException.class | grep "^public class"
javap -p com/fasterxml/jackson/core/JacksonException.class        | grep "^public"
```

`sort -V` is version-aware sort (so `2.22.0` orders above `2.9.1`, which plain lexical `sort` gets
wrong). Result: `JsonProcessingException extends JacksonException` and
`JacksonException extends java.io.IOException`. So an unserializable payload — a permanently
deterministic failure — would have been classified **retryable** by that arm.

Both findings are recorded at the classifier in §8.3, the arm was deleted, and two regression tests
were added to §11.2 so it cannot be reintroduced silently.

**Step 11 — correct an invented method name.**

The same `grep` showed the real call is `messageConverter.toString(messageBody)`. The §5
implementation sketch had written `messageConverter.toStringPayload(messageBody)` — a method that
does not exist and would not compile. Corrected. Recorded here because it is the class of error a
design document is most likely to carry into an implementation PR unchallenged.

### 14.1 What was not done

- **Nothing was compiled or executed.** No file in `mercury-services-commons` was modified; this is a
  design document, not an implementation. Every code block is a proposal.
- **`japicmp`/`revapi` presence was not verified** in the build configuration — hence open question 4.
- **The §9.3 consumer grep was not run** across booking and visibility; those workspaces were not
  available in this session. It is listed as a **release gate**, not as a completed check.
- **The JLS §13.4.4 citation in §8.2 is from the specification, not from an executed experiment.** If
  the reviewer wants empirical confirmation, compile a consumer against `1.0.32`, rebuild only
  `cloud-sdk-api` at `1.0.33`, and run the consumer's tests against the new jar without recompiling.

---

### 15.7 Verification commands for this appendix

```bash
cd /tmp && mkdir rt && cd rt
unzip -o -q ~/.m2/repository/software/amazon/awssdk/sdk-core/2.30.24/sdk-core-2.30.24.jar \
      "software/amazon/awssdk/core/retry/*" "software/amazon/awssdk/core/internal/retry/*"

# default retry mode — look for the RetryMode constant loaded into SDK_DEFAULT_RETRY_MODE
javap -p -c -cp . 'software.amazon.awssdk.core.retry.RetryMode$Resolver' | grep -E "getstatic.*RetryMode"

# what the SDK considers retryable: status codes and exception types
javap -p -c -cp . software.amazon.awssdk.core.internal.retry.SdkDefaultRetrySetting \
  | grep -E "sipush|ldc .*(Exception|IOException)|putstatic.*RETRYABLE"

# attempt counts and backoff constants, per retry mode
cd /tmp && mkdir rj && cd rj
unzip -o -q ~/.m2/repository/software/amazon/awssdk/retries/2.30.24/retries-2.30.24.jar
for c in Legacy Standard Adaptive; do
  javap -p -constants -cp . "software.amazon.awssdk.retries.DefaultRetryStrategy\$$c" \
    | grep -E "MAX_ATTEMPTS|TOKEN_BUCKET|TOKEN_COST"
done
javap -p -c -cp . 'software.amazon.awssdk.retries.DefaultRetryStrategy$Legacy' \
  | sed -n '/static {}/,/^$/p' | grep -E "ldc2_w|Duration|putstatic"
```

Syntax notes: `javap -constants` prints the values of `static final` primitives (which
`-p` alone omits); durations are not compile-time constants, so they must be read from the
`static {}` initializer via `-c` — `sed -n '/static {}/,/^$/p'` isolates that block. `\$` escapes the
nested-class separator so the shell does not treat it as a variable.

**Not verified:** whether any consumer overrides `RetryMode` or `maxAttempts` via
`ClientOverrideConfiguration`, `AWS_RETRY_MODE`, or `AWS_MAX_ATTEMPTS`. All figures above are SDK
defaults; a consumer that overrides them changes the numbers but none of the conclusions.

---

### 16.11 Command log — how the footprint was established

Every command below was run in **Git Bash (POSIX `sh`) on Windows** from the repository root, and is
reproducible as written. Where a `git grep` pipeline has a materially different idiomatic form in
`rg` (ripgrep), `find`, `awk` or `sed`, the equivalent is given alongside with its syntax explained.

#### Conventions used throughout

| Fragment | Meaning |
| --- | --- |
| `git grep -n` | Search **tracked files only**, at the current worktree state. Faster than `grep -r` and automatically honours `.gitignore`, so it never matches `target/`, `node_modules/` or build output. `-n` prints line numbers. |
| `git grep -l` | Print **only file names**, one per matching *file* rather than one per match. Use this when the next stage of the pipeline counts files. |
| `-- '*/main/*.java'` | Everything after `--` is a **pathspec**, not a flag. The quotes are essential: they stop the shell from glob-expanding the pattern itself, so `git` receives the literal pattern and applies it to every tracked path. `*/main/*.java` restricts to production sources and excludes `src/test/`. |
| `-E` | Extended regular expressions — alternation is written unescaped, and `+`, `?`, `()` work without backslashes. In **basic** regex (the default) each of those metacharacters must instead be backslash-escaped. |
| `-i` | Case-insensitive. |
| `-v` | **Invert** the match — print lines that do *not* match. Used to subtract known-irrelevant hits. |
| `\\\|` (without `-E`) | Alternation in **basic** regex, which requires the backslash. With `-E` it is a plain `\|`. |

**Ripgrep equivalent of the pathspec idiom.** `rg` has no `--` pathspec; it uses `-g` (glob), which
may be repeated and negated with a leading `!`:

```bash
rg -n 'pattern' -g '*/main/*.java'          # include only
rg -n 'pattern' -g '!*/test/*'              # exclude
rg -l  'pattern' -g '*.java'                # -l = files-with-matches (same as git grep -l)
```

`rg` also skips `.gitignore`d paths by default, so it matches `git grep`'s scoping without extra
flags. Add `-uu` to disable that if you ever need to search ignored files.

---

#### A. Footprint per module — files importing a cloud-sdk package

```bash
git grep -l "cloudsdk.messaging" -- '*/main/*.java' \
  | cut -d/ -f1 \
  | sort \
  | uniq -c \
  | sort -rn
```

Stage by stage:

- `git grep -l` emits one path per matching **file**, e.g. `visibility/visibility-commons/src/main/java/…`.
- `cut -d/ -f1` — `-d/` sets the **delimiter** to `/`; `-f1` selects **field 1**, i.e. everything
  before the first slash. That is the top-level module name. `cut` does no regex work at all, so it
  is the cheapest way to do this.
- `sort` — `uniq` only collapses **adjacent** duplicates, so the input must be sorted first. Omitting
  this `sort` is the single most common bug in this idiom.
- `uniq -c` — collapse runs of identical lines and **prefix each with its count**.
- `sort -rn` — `-n` sorts **numerically** (so `10` follows `9`, not `1`); `-r` **reverses** it, giving
  descending order. Without `-n` the counts sort lexicographically and `10` lands before `9`.

`awk` equivalent, which replaces the whole four-stage tail with one pass and no pre-sort:

```bash
git grep -l "cloudsdk.messaging" -- '*/main/*.java' \
  | awk -F/ '{ count[$1]++ } END { for (m in count) print count[m], m }' \
  | sort -rn
```

- `-F/` sets the **input field separator** to `/`, making `$1` the module name — the direct analogue
  of `cut -d/ -f1`.
- `{ count[$1]++ }` is the per-line action. `count` is an associative array, auto-created and
  auto-initialised to zero, keyed by module name.
- `END { … }` runs once after the last line of input. `for (m in count)` iterates the keys in
  **unspecified** order, which is why the trailing `sort -rn` is still needed.

Established: the per-module numbers in §16.3.

#### B. Per-module presence check with formatted output

```bash
for m in booking visibility network auth watermill-publisher partner-integrator lambda registration tx-tracking; do
  printf "%-30s messaging=%-3s notification=%-3s\n" "$m" \
    "$(git grep -l 'cloudsdk.messaging'    -- "$m/*.java" 2>/dev/null | wc -l)" \
    "$(git grep -l 'cloudsdk.notification' -- "$m/*.java" 2>/dev/null | wc -l)"
done
```

- `printf "%-30s"` — `%s` is a string field; the `-30` **left-aligns** it in a 30-character column
  (a positive width would right-align). Unlike `echo`, `printf` does not append a newline, hence the
  explicit `\n`.
- `$( … )` is **command substitution**: the inner pipeline runs and its stdout is spliced in as the
  argument. Quoting it (`"$( … )"`) prevents word-splitting on the result.
- `wc -l` counts lines — here, files.
- `2>/dev/null` redirects **file descriptor 2** (stderr) to the null device, suppressing `git grep`'s
  "no such path" noise for module names that do not exist. Note `git grep` exits 1 on no-match, so
  this loop must not be run under `set -e`.

Established: `network`, `auth`, `registration` and `shipping-instruction` have **zero** messaging and
notification usage despite large total cloud-sdk import counts — the single most load-bearing
negative result in §16.3.

#### C. Disambiguating a name collision (`MessagingException`)

The essential step, and the one that changed the conclusion. Four modules define their own class with
that name, so counting textual matches over-reports by roughly 4×. The fix is to read the **import**
rather than the usage:

```bash
for f in <list of files>; do
  printf "%-60s %s\n" "$(basename "$f")" \
    "$(grep -m1 'import.*MessagingException' "$f" || echo '(same-package / none)')"
done
```

- `grep -m1` stops after the **first** match — an import appears once, so this avoids scanning the
  rest of the file.
- `basename "$f"` strips the directory component, leaving the filename for a readable column.
- `|| echo '(…)'` — `grep` exits non-zero when nothing matches, and `||` runs the fallback only in
  that case. Without it the column would be silently blank, and "no import" would be
  indistinguishable from "same-package reference" — which is exactly the distinction being drawn.

Established: the one real hit (`pi-commons/SQSClient.java`, importing
`com.inttra.mercury.cloudsdk.messaging.exception.MessagingException` at line 7), separated from the
`javax.mail` false positive in `libs/email-sender` and the four local classes. See §16.7.

#### D. Locating class *definitions* rather than references

```bash
git grep -l "class MessagingException" -- '*.java'
```

Searching for the **declaration keyword** rather than the bare identifier is what surfaced the four
local classes. A search for `MessagingException` alone returns ~30 lines of noise; `class
MessagingException` returns exactly the definitions.

#### E. External implementors of an interface

```bash
git grep -n "implements QueueMessage\|implements MessagingClient\|implements NotificationService\|implements EventPublisher" -- '*.java'
```

- `\|` is alternation in **basic** regex (no `-E`), so each branch needs the backslash.
- Anchoring on the literal `implements ` keyword distinguishes an *implementor* — which a
  non-`default` interface method would break — from a mere *consumer*, which it would not.

`rg` equivalent, using a proper alternation group:

```bash
rg -n 'implements (QueueMessage|MessagingClient|NotificationService|EventPublisher)' -g '*.java'
```

Established: §16.6 — seven `EventPublisher` implementors and three `QueueMessage` implementors that
§9.2 had not accounted for, and zero for `MessagingClient`.

#### F. Extracting a value from every POM and tabulating it

```bash
for p in $(git ls-files '*pom.xml' | sort); do
  v=$(grep -o '<mercury.commons.version>[^<]*' "$p" | head -1 | sed 's/.*>//')
  [ -n "$v" ] && printf "%-16s %s\n" "$v" "$p"
done | sort
```

- `git ls-files '*pom.xml'` lists tracked files matching the pattern — faster and cleaner than
  `find . -name pom.xml`, because it skips ignored build output automatically.
- `grep -o` prints **only the matched portion** of the line rather than the whole line. The pattern
  `<mercury.commons.version>[^<]*` matches the opening tag plus every following character that is not
  `<` — i.e. the tag and its text content, stopping cleanly at the closing tag. `[^<]` is a **negated
  character class**: "any character except `<`".
- `head -1` keeps only the first occurrence, since the property may be redeclared in a profile.
- `sed 's/.*>//'` performs a **substitution**, `s/PATTERN/REPLACEMENT/`, with an empty replacement —
  i.e. a deletion. `.*>` is **greedy**: `.*` consumes as much as possible while still leaving a `>`
  to match, so it anchors on the **last** `>` on the line and deletes everything up to and including
  it, leaving just the version string. Greediness is precisely what makes this work as a single
  expression.
- `[ -n "$v" ] && …` — `-n` tests for a **non-empty** string, so POMs without the property are
  skipped. The quotes matter: unquoted `$v` on an empty value makes `[ -n ]` a different (and
  always-true) test.

`find` equivalent, for use outside a git repository:

```bash
find . -name pom.xml -not -path '*/target/*' -print0 \
  | xargs -0 grep -l 'mercury.commons.version'
```

- `-name pom.xml` matches the **basename** only; `-path '*/target/*'` matches against the whole
  path, and `-not` negates it, excluding build output that `git ls-files` would have skipped for free.
- `-print0` separates results with a **NUL byte** instead of a newline, and `xargs -0` reads that
  format. This is the only safe way to pipe filenames that may contain spaces — which Windows paths
  frequently do.

`awk` alternative to the `grep | head | sed` chain, doing extraction and printing in one pass:

```bash
awk -F'[<>]' '/mercury.commons.version/ { print $3; exit }' pom.xml
```

- `-F'[<>]'` sets the field separator to a **regex character class** — either `<` or `>`. For the
  line `    <mercury.commons.version>1.0.31-SNAPSHOT</mercury.commons.version>` that splits into
  `    `, `mercury.commons.version`, `1.0.31-SNAPSHOT`, … so `$3` is the value.
- `/pattern/ { action }` is awk's core form: run the action only on lines matching the pattern.
- `exit` stops after the first hit — the equivalent of `head -1`.

Established: the six-way version-pin spread in §16.4.

#### G. Reading non-contiguous regions of a file

```bash
sed -n '70,100p;145,200p' RetryClassifier.java | cat -n
```

- `-n` suppresses sed's default "print every line" behaviour, so **only** explicit `p` commands
  produce output. Without `-n`, every selected line prints twice and every other line prints once.
- `70,100p` is a **line-range address** followed by the `p` (print) command.
- `;` separates multiple commands, so two disjoint ranges are extracted in a single pass — used here
  to read the method body and its private helpers without the 45 lines between them.
- `cat -n` numbers the **output**, which renumbers from 1. That is why §16.9 quotes that file by
  content rather than by absolute line number: the `sed` window and the file's own numbering do not
  agree. When absolute numbers matter, use `grep -n`, or `sed -n '70,100{=;p}'` where `=` prints the
  real line number before each line.

Established: the `RetryClassifier` analysis in §16.9.

#### H. Finding callers while excluding definitions

```bash
git grep -nE "sendMessage\([^;]*,[^;]*,[^;]*\)" -- '*/main/*.java' \
  | grep -viE "public void sendMessage|SendMessageRequest|import"
```

- `\(` and `\)` escape the parentheses so they match **literal** characters rather than forming a
  regex group.
- `[^;]*` — "any run of characters that is not a semicolon" — keeps each match inside a single
  statement, preventing the pattern from spanning two statements on one line.
- Two commas ⇒ three arguments, which is the delay overload's shape.
- The second stage subtracts the **declarations** (`public void sendMessage`), the raw-AWS builder
  form, and imports — leaving only genuine call sites. `-v` inverts, `-i` ignores case, `-E` enables
  `|` alternation.

Established: the delay overload has **no production caller** in mercury-services — only its own unit
test — which is what makes the §16.5 migration low-risk. This is also the query that retired the
§9.2 null-ambiguity hazard, since it returns no three-argument call sites at all.

#### I. Verifying a javadoc claim against source (the S3 retraction)

The claim under test came from a code comment, not from the API: *"the cloud-sdk `MessagingClient`
cannot request SQS system attributes"*. Three checks, one per layer, plus a provenance check:

```bash
# 1. Does the options object expose it?
find . -name 'ReceiveMessageOptions.java' -path '*/main/*' -exec cat -n {} \;

# 2. Does the SQS implementation honour it when building the request?
grep -n "messageSystemAttributeNamesWithStrings" \
  cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/messaging/aws/impl/SqsMessagingClient.java

# 3. Does the received value surface on the returned QueueMessage?
sed -n '70,77p' cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/messaging/aws/impl/SqsMessage.java

# 4. Which release introduced it?
git log --oneline -S "messageSystemAttributeNames" -- cloud-sdk-api cloud-sdk-aws
```

Syntax notes:

- `find . -name 'X.java' -path '*/main/*' -exec cat -n {} \;` — `-name` matches the **basename**;
  `-path` matches the **whole path**, excluding `src/test`. `-exec … {} \;` runs the command once per
  result, with `{}` substituted for the filename. The `\;` terminator must be escaped so the shell
  passes the semicolon to `find` rather than treating it as a command separator. (Use `+` instead of
  `\;` to batch all results into one invocation — faster, but then `cat -n` numbers continuously
  across files rather than restarting per file.)
- **`git log -S <string>`** is the decisive one, and is worth knowing well. It is the **pickaxe**: it
  finds commits where the *number of occurrences* of the string changed — i.e. where the string was
  introduced or removed — rather than commits whose diff merely *mentions* it. That is what
  identifies the introducing commit precisely. `git log -G <regex>` is the related form, matching any
  diff line against a regex; `-S` is the right tool when you want "who added this", `-G` when you want
  "who touched lines like this".
- Restricting with `-- cloud-sdk-api cloud-sdk-aws` scopes the pickaxe to the two modules, which both
  speeds it up and excludes unrelated matches in docs or tests.

Result:

```
ea154df  2026-08-21  ION-12310: close cloud-sdk gaps for mft-s3-aqua-appia aw-bridge; bump to 1.0.32-SNAPSHOT
```

All three layers present; introduced in `1.0.32-SNAPSHOT`; watermill-publisher pinned at
`1.0.28-SNAPSHOT`. The javadoc was accurate against `1.0.28` and stale against `1.0.32`. The proposed
gap was withdrawn — see §16.8.

**Generalisable lesson.** In a repository spanning six commons versions (§16.4), a code comment
records what was true *at the version its author compiled against*, which is not the same as what is
true now. Any gap inferred from a comment must be re-verified against the current API before it
enters a design. Had this one not been checked, `1.0.33` would have shipped a duplicate of an
existing capability.

---

**Caveats on this method.** The sweep is purely static and textual. It cannot see: reflection or
Guice bindings resolved by string name; call sites in generated sources; modules pinned to a commons
version via a parent-POM property this sweep did not follow; or anything outside the two repositories
inspected. It also does not compile anything — the compatibility claims in §16.2 rest on the analysis
in §9 plus the demonstrated absence of the specific patterns that analysis flagged, **not** on a
build. Running `japicmp` (§11.3) against the released `1.0.32` artifact remains the authoritative
check before release.
