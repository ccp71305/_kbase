# PIBL-ES Lambda build failure — deployment package exceeds Lambda 250 MB unzipped limit

- **Date:** 2026-08-29
- **Module:** `partner-integrator/pi-bl-es-lambda`
- **Jenkins job:** PIBL-ES Lambda (deploys via `aws lambda update-function-code`)
- **Jira / related:** ION-16417 (partner-integrator AWS SDK 1.x → 2.x / cloud-sdk upgrade)
- **Triggering commit:** `8bba065f0e` — *ION-16417: partner-integrator AWS SDK 1.x -> 2.x (cloud-sdk) upgrade*
- **Author of investigation:** copilot (claude-opus-4.8)

---

## 1. Summary

The PIBL-ES Lambda Jenkins job fails at the deploy step with:

```
An error occurred (InvalidParameterValueException) when calling the UpdateFunctionCode operation:
Unzipped size must be smaller than 262144000 bytes
Build step 'Execute shell' marked build as failure
```

`262144000 bytes = 250 MB` is AWS Lambda's **hard limit on the total *unzipped* size** of a
function's deployment package (function code + all attached layers combined). The build itself
compiles and packages fine — the failure is purely a **package-size** problem at deploy time.

**Measured facts (this investigation):**

| Artifact | Zipped | Unzipped |
|---|---|---|
| `pi-bl-es-lambda-1.0.jar` (shaded, current `develop`) | 138.0 MB | **334.4 MB (350,672,249 bytes)** |
| Lambda limit | — | 250.0 MB (262,144,000 bytes) |
| **Over limit by** | — | **84.4 MB** |

**Root cause:** The AWS SDK 1.x → 2.x upgrade (ION-16417) replaced the single, lean AWS SDK v1
`dynamo-client` artifact with the in-house `cloud-sdk-aws` aggregate, which bundles the AWS SDK 2.x
clients for **every** service (S3, SES, SNS, SQS, SSM, DynamoDB, transfer-manager), **three** HTTP
clients (Apache, URL-connection, CRT + native binary) **and** a transitive copy of AWS SDK **v1**.
That extra weight, stacked on top of the module's already-heavy `org.elasticsearch:elasticsearch`
server jar and the full Dropwizard/Jetty/POI/MyBatis tree dragged in by `commons`, pushed the
shaded fat-jar over the 250 MB unzipped ceiling for the first time.

**Recommended fix (validated):** Trim the fat jar via Maven `<exclusions>` on the `commons`,
`cloud-sdk-api` **and** `cloud-sdk-aws` dependencies to drop the transitive libraries this Lambda
never loads, plus a two-line source cleanup in `Indexer.java` (drop the dead `@Timed` annotation and
swap Jetty's `RuntimeIOException` for the JDK `java.io.UncheckedIOException`) so the whole
Dropwizard/Jetty/Jersey web stack can be removed. This takes the package from 334.4 MB →
**146.5 MB unzipped (103 MB under the limit)** with **all 93 unit tests still green**.

> **Note on the exclusion scope (PR review follow-up).** The web-stack (`dropwizard-core` →
> jetty/jersey/hk2) is declared by **all three** in-house artifacts (`commons`, `cloud-sdk-api`,
> `cloud-sdk-aws`); excluding it from only one lets Maven resolve it through the next, so the
> exclusions must be applied to all three. See §10.

---

## 2. Environment / how the Lambda is packaged

`pi-bl-es-lambda` builds a **shaded fat jar** (`maven-shade-plugin` 3.5.3) that *is* the Lambda
deployment package — the `.jar` is uploaded directly by the Jenkins `aws lambda update-function-code`
step. The shade config currently has **no `minimizeJar`, no filters and no artifact exclusions**, so
every compile/runtime dependency is embedded verbatim.

What the Lambda code actually needs at runtime:
- DynamoDB access via cloud-sdk (`DynamoDbClientConfig` / `DynamoRepositoryFactory` → AWS SDK 2.x
  `dynamodb` + `dynamodb-enhanced` + the **Apache** sync HTTP client).
- Elasticsearch indexing via the **Jest** client (`io.searchbox.*`, pulled through `commons`).
- `com.amazonaws.services.lambda.runtime.events.*` (aws-lambda-java-events 3.x).
- Jackson, Lombok, SLF4J/Logback, commons-lang3, and the `commons` `JsonSupport` util.

Everything else in the jar is dead weight for this function.

---

## 3. Root-cause analysis — where the 334 MB comes from

Footprint by dependency group, from the resolved classpath (zipped `.m2` jar sizes; unzipped is
~2.3× larger):

| Group | Zipped | Notes |
|---|---:|---|
| *(everything else — jackson, guava, guice, jaxb, gson, commons-\*, netty, asm/nashorn…)* | 44.9 MB | mixed; some removable |
| **aws-sdk-v2** (`software.amazon.awssdk:*` 2.30.24) | 40.3 MB | ssm, sesv2, **s3**, **s3-transfer-manager**, sns, sqs, dynamodb, dynamodb-enhanced + **3 HTTP clients** (apache, url-connection, aws-crt + native) + sso/ssooidc |
| **elasticsearch + lucene** (`org.elasticsearch:elasticsearch` 8.17.0) | 35.5 MB | full ES **server** + 13 Lucene 9.12 modules + log4j2 + grok/joni + tdigest + hppc + native — used **only** to build query JSON strings |
| **poi + xmlbeans** (`org.apache.poi:*` 5.3.0) | 12.7 MB | Excel/OOXML — **never used** by this Lambda (from `commons`) |
| **dropwizard + jetty + jersey** | 8.7 MB | full web stack — **never used** by a Lambda (from `commons`) |
| **mysql + mybatis** | 4.0 MB | JDBC/ORM — **never used** by this Lambda (from `commons`) |
| **aws-sdk-v1** (`com.amazonaws:aws-java-sdk-*` 1.12.730) | 3.8 MB | v1 core/sqs/sns/s3/kms — leftover, **not used** (from `cloud-sdk-aws`) |

### 3.1 Why the upgrade tipped it over (the diff)

`git show 8bba065f0e -- partner-integrator/pi-bl-es-lambda/pom.xml`:

```diff
-        <artifactId>dynamo-client</artifactId>          # single, lean AWS SDK v1 jar
-        <version>${mercury.dynamodbclient.version}</version>
+        <artifactId>cloud-sdk-api</artifactId>
+        <artifactId>cloud-sdk-aws</artifactId>          # AWS SDK 2.x aggregate: ALL services + 3 HTTP clients + AWS SDK v1
```

`cloud-sdk-aws` is a shared, service-agnostic aggregate: it declares the AWS SDK 2.x clients for
S3, SES, SNS, SQS, SSM and DynamoDB, all three SDK HTTP clients (including the `aws-crt` native
binary), and a transitive AWS SDK **v1** tree. Swapping the ~4 MB `dynamo-client` for this ~40+ MB
aggregate is what crossed the 250 MB unzipped line. The `elasticsearch`, `commons`, POI, Jetty,
MySQL weight was *already present before* the upgrade — the module was simply sitting just under the
ceiling, and the SDK upgrade removed the remaining headroom.

### 3.2 The Elasticsearch server jar is 35 MB used only for query strings

`Indexer.java` performs all ES I/O through the **Jest** client, and imports
`org.elasticsearch.index.query.QueryBuilders` / `BoolQueryBuilder` / `SearchSourceBuilder` **only**
to build a query as a JSON string:

```java
BoolQueryBuilder queryBuilder = QueryBuilders.boolQuery().must(QueryBuilders.termQuery("siId", siId));
return SearchSourceBuilder.searchSource().query(queryBuilder);   // -> .toString() JSON
```

Pulling the entire ES **server** distribution (+ Lucene, log4j2, grok, native libs) to assemble a
one-line term query is disproportionate. It is not removed in the recommended fix below (kept for
zero-risk), but see §6 for the follow-up to eliminate it.

---

## 4. Options considered

| # | Option | Effect on 250 MB limit | Risk / effort | Verdict |
|---|---|---|---|---|
| A | **Trim unused transitive deps via `<exclusions>`** (recommended) | 334 → **178 MB**, under limit | Low — deps-only, all tests green | ✅ **Adopt now** |
| B | Add `<minimizeJar>` + shade filters | Helps, but brittle (reflection/service loaders in ES/AWS SDK need explicit `filter` keeps) | Medium | Optional add-on to A |
| C | Replace ES server jar with lightweight query building (Jest/`co.elastic.clients` or hand-built JSON) | Extra ~35 MB zipped / ~80 MB unzipped saved | Medium — code change + tests | ✅ Follow-up (§6) |
| D | **Lambda Layers** | ❌ **Does not help** — the 262,144,000 limit is function code **+ layers combined** | — | Rejected |
| E | **Container image** deployment (up to 10 GB) | Removes the limit entirely | High — Jenkins/ECR/base-image rework | Fallback only |

> **Important:** Moving jars to a Lambda **Layer does not solve this** — AWS applies the 250 MB
> unzipped limit to the *sum* of the function package and all layers. Only reducing total bytes
> (Options A/B/C) or switching to a container image (E) works.

---

## 5. Recommended solution (validated)

Add Maven `<exclusions>` to the `commons` and `cloud-sdk-aws` dependencies in
`partner-integrator/pi-bl-es-lambda/pom.xml` so the shaded jar stops embedding libraries this
Lambda never loads:

- **From `commons`:** the whole Dropwizard / Jetty / Jersey / HK2 web stack, MySQL + MyBatis,
  Apache POI + XmlBeans + curvesapi, jsoup, spring-security-crypto.
- **From `cloud-sdk-aws`:** AWS SDK 2.x `s3`, `s3-transfer-manager`, `sesv2`, `sns`, `sqs`, `ssm`;
  the redundant `url-connection-client` and `aws-crt-client` (+ native `aws-crt`); the AWS SDK **v1**
  `aws-java-sdk-core/sqs/sns/s3`; `amazon-sqs-java-extended-client-lib`; `handlebars`; `javax.mail`.

> **Do NOT exclude `software.amazon.awssdk:apache-client`.** cloud-sdk's `DynamoDbClientConfig`
> instantiates `ApacheHttpClient` as the sync HTTP client; removing it fails at runtime with
> `NoClassDefFoundError: software/amazon/awssdk/http/apache/ApacheHttpClient`
> (confirmed — `HandlerSupportTest.newBLDao_withEnvironment_buildsDaoForPrefixedTable`). Keep exactly
> **one** sync HTTP client (Apache) and drop the other two.

The exact change applied (`git diff` on `pi-bl-es-lambda/pom.xml`):

```xml
<dependency>
    <groupId>com.inttra.mercury</groupId>
    <artifactId>commons</artifactId>
    <version>${mercury.commons.version}</version>
    <exclusions>
        <exclusion><groupId>io.dropwizard</groupId><artifactId>*</artifactId></exclusion>
        <exclusion><groupId>io.dropwizard.metrics</groupId><artifactId>*</artifactId></exclusion>
        <exclusion><groupId>io.dropwizard.logback</groupId><artifactId>*</artifactId></exclusion>
        <exclusion><groupId>ch.qos.logback.access</groupId><artifactId>*</artifactId></exclusion>
        <exclusion><groupId>org.eclipse.jetty</groupId><artifactId>*</artifactId></exclusion>
        <exclusion><groupId>org.eclipse.jetty.ee10</groupId><artifactId>*</artifactId></exclusion>
        <exclusion><groupId>org.eclipse.jetty.toolchain.setuid</groupId><artifactId>*</artifactId></exclusion>
        <exclusion><groupId>org.glassfish.jersey.core</groupId><artifactId>*</artifactId></exclusion>
        <exclusion><groupId>org.glassfish.jersey.containers</groupId><artifactId>*</artifactId></exclusion>
        <exclusion><groupId>org.glassfish.jersey.ext</groupId><artifactId>*</artifactId></exclusion>
        <exclusion><groupId>org.glassfish.jersey.inject</groupId><artifactId>*</artifactId></exclusion>
        <exclusion><groupId>org.glassfish.jersey.media</groupId><artifactId>*</artifactId></exclusion>
        <exclusion><groupId>org.glassfish.hk2</groupId><artifactId>*</artifactId></exclusion>
        <exclusion><groupId>org.glassfish.hk2.external</groupId><artifactId>*</artifactId></exclusion>
        <exclusion><groupId>mysql</groupId><artifactId>*</artifactId></exclusion>
        <exclusion><groupId>org.mybatis</groupId><artifactId>*</artifactId></exclusion>
        <exclusion><groupId>org.apache.poi</groupId><artifactId>*</artifactId></exclusion>
        <exclusion><groupId>org.apache.xmlbeans</groupId><artifactId>*</artifactId></exclusion>
        <exclusion><groupId>com.github.virtuald</groupId><artifactId>curvesapi</artifactId></exclusion>
        <exclusion><groupId>org.jsoup</groupId><artifactId>jsoup</artifactId></exclusion>
        <exclusion><groupId>org.springframework.security</groupId><artifactId>*</artifactId></exclusion>
    </exclusions>
</dependency>
<dependency>
    <groupId>com.inttra.mercury</groupId>
    <artifactId>cloud-sdk-api</artifactId>
</dependency>
<dependency>
    <groupId>com.inttra.mercury</groupId>
    <artifactId>cloud-sdk-aws</artifactId>
    <exclusions>
        <exclusion><groupId>software.amazon.awssdk</groupId><artifactId>s3</artifactId></exclusion>
        <exclusion><groupId>software.amazon.awssdk</groupId><artifactId>s3-transfer-manager</artifactId></exclusion>
        <exclusion><groupId>software.amazon.awssdk</groupId><artifactId>sesv2</artifactId></exclusion>
        <exclusion><groupId>software.amazon.awssdk</groupId><artifactId>sns</artifactId></exclusion>
        <exclusion><groupId>software.amazon.awssdk</groupId><artifactId>sqs</artifactId></exclusion>
        <exclusion><groupId>software.amazon.awssdk</groupId><artifactId>ssm</artifactId></exclusion>
        <exclusion><groupId>software.amazon.awssdk</groupId><artifactId>aws-crt-client</artifactId></exclusion>
        <exclusion><groupId>software.amazon.awssdk.crt</groupId><artifactId>aws-crt</artifactId></exclusion>
        <exclusion><groupId>software.amazon.awssdk</groupId><artifactId>url-connection-client</artifactId></exclusion>
        <exclusion><groupId>com.amazonaws</groupId><artifactId>amazon-sqs-java-extended-client-lib</artifactId></exclusion>
        <exclusion><groupId>com.amazonaws</groupId><artifactId>aws-java-sdk-core</artifactId></exclusion>
        <exclusion><groupId>com.amazonaws</groupId><artifactId>aws-java-sdk-sqs</artifactId></exclusion>
        <exclusion><groupId>com.amazonaws</groupId><artifactId>aws-java-sdk-sns</artifactId></exclusion>
        <exclusion><groupId>com.amazonaws</groupId><artifactId>aws-java-sdk-s3</artifactId></exclusion>
        <exclusion><groupId>com.github.jknack</groupId><artifactId>handlebars</artifactId></exclusion>
        <exclusion><groupId>com.sun.mail</groupId><artifactId>javax.mail</artifactId></exclusion>
    </exclusions>
</dependency>
```

> Note: excluding `s3`/`sqs`/`sns`/`ssm`/`sesv2` here is safe **for this Lambda only** because it
> uses none of them. Other `pi-*` submodules that share `cloud-sdk-aws` are unaffected — exclusions
> are scoped to this POM.

---

## 6. Validation results

Built and tested locally on `develop` with the exclusions applied:

| Metric | Before (current `develop`) | After (recommended fix) |
|---|---:|---:|
| Shaded jar, zipped | 138.0 MB | **76.9 MB** |
| Shaded jar, **unzipped** | 334.4 MB (350,672,249 B) | **177.7 MB (186,299,610 B)** |
| vs 250 MB limit | ❌ over by 84.4 MB | ✅ **under by 72.3 MB** |
| Unit tests (`mvn -pl pi-bl-es-lambda test`) | 93 pass | **93 pass, 0 failures, 0 errors** |

Commands:
```bash
mvn -pl partner-integrator/pi-bl-es-lambda package        # BUILD SUCCESS, 93/93 tests
# unzipped size measured from the shaded jar's zip entry lengths
```

---

## 7. Residual / future work

1. **Eliminate the Elasticsearch server jar (Option C).** Replace the `QueryBuilders` /
   `SearchSourceBuilder` usage in `Indexer.java` with a hand-built query JSON or the lightweight
   `co.elastic.clients:elasticsearch-java` client, then drop `org.elasticsearch:elasticsearch`.
   Saves a further ~35 MB zipped / ~80 MB unzipped and aligns with the planned Jest → OpenSearch/ES
   client migration. Requires a code change + test updates.
2. **Add `<minimizeJar>` + shade filters (Option B)** as belt-and-braces, keeping explicit `filter`
   entries for AWS SDK / Lucene service-loader and resource files.
3. **Consider container-image packaging (Option E)** if the function later needs to grow again.
4. **Push the exclusion pattern upstream:** consider a slimmer `cloud-sdk-aws-dynamodb`-only
   artifact in `mercury-services-commons` so every Lambda module doesn't have to hand-exclude the
   unused services.

## 8. Rollback

The change is confined to `partner-integrator/pi-bl-es-lambda/pom.xml`. Reverting that file's
`<exclusions>` restores the previous (over-limit) build. No source, DynamoDB schema, ES mapping, or
wire-format changes are involved.

## 9. References

- Error: `UpdateFunctionCode … Unzipped size must be smaller than 262144000 bytes` (Jenkins PIBL-ES).
- Triggering commit: `8bba065f0e` (ION-16417).
- AWS Lambda quotas: deployment package **250 MB unzipped**, applied to function code **+ layers**.
- Related design docs: `2026-0731-pi-aws-upgrade-design.md`, `2026-08-20-pi-awsupgrade-refactoring.md`,
  `2026-0825-pi-refactor-pr-fix.md`, `2026-08-21-pi-awsupgrade-confluence-design.md`.

---

## 10. PR review comment — "wildcard artifact exclusions do not take effect" (importance 8)

**Comment (paraphrased):** *Maven dependency exclusions do not support wildcard artifact IDs, so
none of these exclusions will take effect and the fat-jar will remain the same size. Enumerate each
concrete artifact instead.*

**Assessment: does it tally? — Partially, but the stated mechanism is incorrect.**

1. **Wildcard `<artifactId>*</artifactId>` exclusions ARE supported.** Maven has supported `*`
   wildcards in both `groupId` and `artifactId` of an exclusion since **Maven 3.2.1** (MNG-5600).
   This build runs on **Maven 3.9.11**. Empirical proof from `dependency:tree` on the committed POM:
   the wildcard exclusions for `org.apache.poi:*`, `org.apache.xmlbeans:*`, `mysql:*`,
   `org.mybatis:*` and `org.springframework.security:*` **did** take effect and the shaded jar
   dropped from **334.4 MB → 177.7 MB unzipped**. If wildcards were ignored, neither would have
   happened. So the premise "none of these will take effect / same size" is disproved.

2. **The reviewer nonetheless spotted a real, separate gap.** Dropwizard/Jetty/Jersey/HK2 were still
   in the jar — not because the wildcard syntax fails, but because `dropwizard-core` is declared by
   **all three** in-house aggregates (`commons`, `cloud-sdk-api`, `cloud-sdk-aws`). Excluding it from
   only `commons` (and later `cloud-sdk-api`) made Maven simply resolve it via the next un-excluded
   path (`cloud-sdk-aws`) — classic transitive whack-a-mole. Switching to *concrete* artifact IDs
   would **not** have fixed this either; the fix is to apply the exclusions on **every** path.

3. **A second reason the web stack could not just be excluded:** the Lambda's own
   `Indexer.java` actually *used* two classes from it — `com.codahale.metrics.annotation.@Timed`
   (Dropwizard metrics) and `org.eclipse.jetty.io.RuntimeIOException` (Jetty). Blanket-excluding the
   stack therefore broke compilation until those were removed.

**Resolution applied:**
- Added the web-stack exclusions to **all three** in-house deps (`commons`, `cloud-sdk-api`,
  `cloud-sdk-aws`).
- `Indexer.java`: removed the dead `@Timed` annotation (a no-op here — the handler does
  `new Indexer(jestClient)` with no metrics registry / Guice AOP to honour it) and replaced Jetty's
  `RuntimeIOException` with the JDK-standard `java.io.UncheckedIOException` (identical semantics:
  an unchecked wrapper around `IOException`). `IndexerTest.java` updated to match.
- Result: Dropwizard/Jetty/Jersey/HK2/Codahale now fully **absent** from the tree; shaded jar
  **146.5 MB unzipped (103.5 MB under the 250 MB limit)**; **93/93 tests pass**.

**On wildcard vs concrete artifact IDs:** kept wildcards — they are valid, and are *more* robust than
enumerating concrete IDs because they also catch newly-added transitive artifacts in these groups on
future `commons`/cloud-sdk bumps. `apache-client` is deliberately **not** excluded (cloud-sdk needs
`ApacheHttpClient`).

**Draft reply to reviewer:**

> Thanks — good catch that the web-stack bundles were still shipping. Two clarifications: (1)
> wildcard `<artifactId>*</artifactId>` exclusions *are* supported (Maven 3.2.1+/MNG-5600; we're on
> 3.9.11) and they demonstrably worked here — POI, XmlBeans, MySQL, MyBatis and Spring-Security were
> all dropped and the jar went 334→178 MB. (2) The reason Dropwizard/Jetty/Jersey survived is that
> `dropwizard-core` is pulled by *all three* in-house aggregates (commons, cloud-sdk-api,
> cloud-sdk-aws), so excluding it from one just re-resolves it via another — concrete IDs wouldn't
> have helped. Fixed by excluding on all three paths and removing the only real usages in
> `Indexer.java` (`@Timed`, Jetty `RuntimeIOException` → `java.io.UncheckedIOException`). Tree is now
> clean of the web stack; jar is 146.5 MB unzipped, all 93 tests green.

### Final measurements

| Stage | Unzipped | vs 250 MB limit |
|---|---:|---:|
| Original (`develop`) | 334.4 MB | ❌ over by 84.4 MB |
| Deps-only exclusions (first commit `b6463e8e14`) | 177.7 MB | ✅ under by 72.3 MB |
| **+ 3-path exclusions + `Indexer.java` cleanup** | **146.5 MB** | ✅ **under by 103.5 MB** |

---

## 11. Runbook — exact commands used (investigation -> fix -> review pushback)

All commands were run from the repo root
`C:\Users\arijit.kundu\projects\mercury-services` on Windows PowerShell with Maven 3.9.11 / JDK 17.
`--no-pager` is used on git so output is not swallowed by a pager. `-pl <module>` restricts Maven to a
single reactor module. Unzipped size is measured from the jar's central-directory entry lengths (the
Lambda limit is on the *uncompressed* bytes, which a normal `ls`/`Length` on the zipped jar does not
show).

### Phase 1 — Reproduce & locate the bloat

```powershell
# 1.1 Recent history of the module POM — find the commit that changed dependencies
git --no-pager log --oneline -15 -- partner-integrator/pi-bl-es-lambda/pom.xml
#   -> 8bba065f0e ION-16417: partner-integrator AWS SDK 1.x -> 2.x (cloud-sdk) upgrade

# 1.2 Show exactly what that upgrade did to the POM (dependency swap)
git --no-pager show 8bba065f0e -- partner-integrator/pi-bl-es-lambda/pom.xml
#   -> confirms dynamo-client (v1) replaced by cloud-sdk-api + cloud-sdk-aws

# 1.3 Full dependency tree (which jars get shaded in). Written to a temp file, then searched.
mvn -pl partner-integrator/pi-bl-es-lambda dependency:tree | Out-File $env:TEMP\pibl-tree.txt -Encoding utf8
#   Inspect the big contributors:
#   elasticsearch server + Lucene, AWS SDK v2 (all services), AWS SDK v1, Dropwizard/Jetty, POI, MySQL

# 1.4 Build the actual Lambda deployment artifact (the shaded fat-jar)
mvn -pl partner-integrator/pi-bl-es-lambda package -DskipTests

# 1.5 Zipped size (what a file listing shows — NOT the limit that failed)
Get-ChildItem partner-integrator/pi-bl-es-lambda/target/*.jar |
  Select-Object Name,@{N='MB';E={[math]::Round($_.Length/1MB,1)}}
#   -> pi-bl-es-lambda-1.0.jar  138 MB (zipped)

# 1.6 UNZIPPED size = sum of every entry's uncompressed Length (this is what Lambda checks)
Add-Type -AssemblyName System.IO.Compression.FileSystem
$p = Resolve-Path "partner-integrator/pi-bl-es-lambda/target/pi-bl-es-lambda-1.0.jar"
$zip = [System.IO.Compression.ZipFile]::OpenRead($p)
$total = ($zip.Entries | Measure-Object -Property Length -Sum).Sum
$zip.Dispose()
"{0:N0} bytes = {1} MB" -f $total, [math]::Round($total/1MB,1)
#   -> 350,672,249 bytes = 334.4 MB  (limit 262,144,000 = 250 MB; over by 84 MB)

# 1.7 Footprint by dependency group (zipped jar sizes from the resolved classpath)
mvn -pl partner-integrator/pi-bl-es-lambda dependency:build-classpath `
  "-Dmdep.outputFile=$env:TEMP\pibl-cp.txt"
$cp = (Get-Content "$env:TEMP\pibl-cp.txt") -split ';' | Where-Object { $_ -like '*.jar' }
#   then group $cp by path prefix (org\elasticsearch, software\amazon, io\dropwizard, ...) and sum Length
#   -> aws-sdk-v2 40MB, elasticsearch+lucene 35MB, poi 12.7MB, dropwizard/jetty 8.7MB, mysql 4MB, aws-v1 3.8MB
```

#### Git Bash / Unix equivalents for steps 1.5–1.7

Same three measurements using tools shipped with Git Bash (GNU coreutils `find`/`stat`/`du`/`awk`/`sed`
plus the JDK `jar`). **Note:** a `.jar` is a **ZIP** archive, so `tar` cannot read it — use `jar tvf`
(always present with the JDK) or `unzip -l` (if installed) to enumerate entries.

```bash
# 1.5 (bash) Zipped size — plain file listing / du / find+awk
ls -l  partner-integrator/pi-bl-es-lambda/target/pi-bl-es-lambda-1.0.jar      # raw bytes in col 5
du -m  partner-integrator/pi-bl-es-lambda/target/pi-bl-es-lambda-1.0.jar      # size in whole MB
#   decimals via GNU find -printf (name + bytes) piped to awk:
find partner-integrator/pi-bl-es-lambda/target -name '*.jar' -printf '%f %s\n' \
  | awk '{printf "%-32s %.1f MB (zipped)\n", $1, $2/1048576}'
#   -> pi-bl-es-lambda-1.0.jar        138.0 MB (zipped)

# 1.6 (bash) UNZIPPED size — sum of every entry's *uncompressed* size
#   Option A (portable — JDK jar tool; first column of `jar tvf` is the uncompressed byte size):
jar tvf partner-integrator/pi-bl-es-lambda/target/pi-bl-es-lambda-1.0.jar \
  | awk '{sum += $1} END {printf "%d bytes = %.1f MB\n", sum, sum/1048576}'
#   Option B (if `unzip` is available — its listing footer already totals uncompressed bytes):
unzip -l partner-integrator/pi-bl-es-lambda/target/pi-bl-es-lambda-1.0.jar \
  | tail -1 | awk '{printf "%d bytes = %.1f MB\n", $1, $1/1048576}'
#   -> 350,672,249 bytes = 334.4 MB   (limit 262,144,000 = 250 MB; over by 84 MB)

# 1.7 (bash) Footprint by dependency group (zipped jar sizes from the resolved classpath)
mvn -pl partner-integrator/pi-bl-es-lambda dependency:build-classpath \
  -Dmdep.outputFile=/tmp/pibl-cp.txt
#   The Windows mvn writes ';'-separated paths with backslashes; tr normalises both so the
#   paths are usable in Git Bash. Emit "<bytes> <path>" per jar via stat:
tr ';' '\n' < /tmp/pibl-cp.txt | tr '\\' '/' | grep -i '\.jar$' \
  | while read -r jar; do printf '%s %s\n' "$(stat -c %s "$jar")" "$jar"; done > /tmp/pibl-jars.txt
#   Grand total + jar count:
awk '{s+=$1} END{printf "classpath total: %.1f MB across %d jars\n", s/1048576, NR}' /tmp/pibl-jars.txt
#   Group by the two .m2 path segments after '/repository/' (approx groupId root), largest first:
awk '{ n=split($2,p,"/"); for(i=1;i<=n;i++) if(p[i]=="repository") break;
       g[p[i+1]"/"p[i+2]] += $1 }
     END { for(k in g) printf "%-30s %.1f MB\n", k, g[k]/1048576 }' /tmp/pibl-jars.txt \
  | sort -k2 -nr
#   -> software/amazon 40MB, org/elasticsearch 35MB, org/apache 20MB (poi+lucene share org/apache), ...
```

> `stat -c %s <file>` prints a file's size in bytes (GNU coreutils). `sed -E` / `awk` split the `.m2`
> path `.../repository/<groupId>/<artifactId>/<version>/<file>.jar` to derive a grouping key. If your
> Git Bash `mvn` emits a `:`-separated classpath (rare on Windows), swap `tr ';' '\n'` for
> `tr ':' '\n'` — but beware Windows drive letters (`C:\...`) also contain a colon.

### Phase 2 — First fix (dependency exclusions only)

```powershell
# 2.1 Back up the POM before editing
Copy-Item partner-integrator/pi-bl-es-lambda/pom.xml partner-integrator/pi-bl-es-lambda/pom.xml.bak

# 2.2 (edit) add <exclusions> to the commons and cloud-sdk-aws dependencies

# 2.3 Rebuild + run tests + re-measure unzipped size (repeat of 1.4/1.6)
mvn -pl partner-integrator/pi-bl-es-lambda package
#   First attempt EXCLUDED apache-client -> test failure:
#     HandlerSupportTest ... NoClassDefFoundError: software/amazon/awssdk/http/apache/ApacheHttpClient
#   Tripwire: cloud-sdk DynamoDbClientConfig needs ApacheHttpClient. Fix: keep apache-client,
#   exclude url-connection-client instead.

mvn -pl partner-integrator/pi-bl-es-lambda test          # -> Tests run: 93, Failures: 0, Errors: 0
#   Re-measured unzipped: 186,299,610 bytes = 177.7 MB (under limit by 72 MB)

# 2.4 Remove the backup once satisfied
Remove-Item partner-integrator/pi-bl-es-lambda/pom.xml.bak
```

### Phase 3 — Commit the first fix on a feature branch

```powershell
git checkout -b feature/ION-16417-pibl-es-lambda-size-fix        # new branch off develop
git add partner-integrator/pi-bl-es-lambda/pom.xml
git commit -m "ION-16417: shrink pi-bl-es-lambda deploy package under Lambda 250MB limit ..."
git push --set-upstream origin feature/ION-16417-pibl-es-lambda-size-fix   # push + set upstream tracking
#   Verify:
git --no-pager log -1 --oneline                                  # -> b6463e8e14 ...
git rev-parse --abbrev-ref --symbolic-full-name '@{u}'           # -> origin/feature/ION-16417-...
```
> Note: `partner-integrator/docs/**` is git-ignored (`.gitignore:110 **/docs/`), so the design docs are
> local artifacts and never appear in the commit — only the POM/source are committed.

### Phase 4 — Review pushback ("wildcard exclusions don't work") + full web-stack removal

```powershell
# 4.1 Re-run the tree on the committed POM and check which excluded groups actually disappeared
mvn -pl partner-integrator/pi-bl-es-lambda dependency:tree | Out-File $env:TEMP\pibl-tree2.txt -Encoding utf8
$t = Get-Content $env:TEMP\pibl-tree2.txt
foreach ($g in 'io.dropwizard','org.eclipse.jetty','org.apache.poi','mysql:','software.amazon.awssdk:s3') {
  "{0,-28} {1}" -f $g, $(if(($t|Select-String -SimpleMatch $g).Count -eq 0){'absent'}else{'PRESENT'})
}
#   -> poi/mysql/s3 absent (wildcards DID work); dropwizard/jetty still PRESENT

# 4.2 Find WHERE the surviving dropwizard-core comes from (its nearest top-level '+- com.inttra' parent)
$ln = ($t | Select-String 'io.dropwizard:dropwizard-core').LineNumber
for($i=$ln-1;$i -ge 0;$i--){ if($t[$i] -match '^\[INFO\] \+\- '){ $t[$i]; break } }
#   -> came from cloud-sdk-api; after excluding there too it re-appeared under cloud-sdk-aws (whack-a-mole)

# 4.3 (edit) add the same web-stack exclusions to cloud-sdk-api AND cloud-sdk-aws, then rebuild
mvn -pl partner-integrator/pi-bl-es-lambda package
#   Tripwire: COMPILATION FAILURE — Indexer.java used two classes from the excluded stack:
#     com.codahale.metrics.annotation.Timed  and  org.eclipse.jetty.io.RuntimeIOException

# 4.4 Confirm exactly where those symbols are used (main + test)
#     (built-in grep over **/pi-bl-es-lambda/**/*.java for: codahale|jetty|Timed|RuntimeIOException)

# 4.5 (edit) Indexer.java: drop @Timed; RuntimeIOException -> java.io.UncheckedIOException (3 throw sites)
$f = "partner-integrator/pi-bl-es-lambda/src/main/java/com/inttra/mercury/pi/elasticsearch/Indexer.java"
(Get-Content $f -Raw) -replace 'new RuntimeIOException\(e\)', 'new UncheckedIOException(e)' |
  Set-Content $f -NoNewline
#     IndexerTest.java: import + 3x assertThrows(RuntimeIOException.class) -> UncheckedIOException.class
$tf = "partner-integrator/pi-bl-es-lambda/src/test/java/com/inttra/mercury/pi/elasticsearch/IndexerTest.java"
$c = (Get-Content $tf -Raw) -replace 'RuntimeIOException','UncheckedIOException'
$c = $c -replace 'import java\.io\.IOException;', "import java.io.IOException;`r`nimport java.io.UncheckedIOException;"
Set-Content $tf $c -NoNewline

# 4.6 Rebuild, test, re-measure, and confirm the web stack is gone
mvn -pl partner-integrator/pi-bl-es-lambda package            # -> BUILD SUCCESS, Tests run: 93, 0 failures
mvn -pl partner-integrator/pi-bl-es-lambda dependency:tree | Out-File $env:TEMP\pibl-tree5.txt -Encoding utf8
#   dropwizard/jetty/jersey/hk2/codahale -> absent; unzipped 153,598,295 bytes = 146.5 MB (under by 103.5 MB)

# 4.7 Commit + push the review fix (branch already tracks upstream, so a bare push is enough)
git add partner-integrator/pi-bl-es-lambda/pom.xml `
        partner-integrator/pi-bl-es-lambda/src/main/java/com/inttra/mercury/pi/elasticsearch/Indexer.java `
        partner-integrator/pi-bl-es-lambda/src/test/java/com/inttra/mercury/pi/elasticsearch/IndexerTest.java
git commit -m "ION-16417: fully drop Dropwizard/Jetty/Jersey from pi-bl-es-lambda fat-jar (PR review) ..."
git push                                                     # -> 83b4a5d9f7 ; PR #1219
```

### Phase 5 — `@Timed` pushback: prove it was inert, add real timing

```powershell
# 5.1 Show how Indexer is instantiated and search for any metrics/AOP interception in the module
#     view IndexerHandler.java  -> `new Indexer(newJestClient())` (plain POJO)
#     grep **/pi-bl-es-lambda/**/*.java for:
#        MetricRegistry | bindInterceptor | InstrumentedResourceMethod | new Indexer | Guice | createInjector
#     -> no MetricRegistry, no Guice injector, no Jersey listener => @Timed had nothing to honour it

# 5.2 (edit) Indexer.index(): measure with System.nanoTime() and log elapsed ms (dependency-free)
mvn -pl partner-integrator/pi-bl-es-lambda package          # -> BUILD SUCCESS, Tests run: 93; size unchanged 146.5 MB

# 5.3 Commit + push
git add partner-integrator/pi-bl-es-lambda/src/main/java/com/inttra/mercury/pi/elasticsearch/Indexer.java
git commit -m "ION-16417: log real ES index duration in place of inert @Timed ..."
git push                                                    # -> 886e867480 ; PR #1219
```

### Command reference — what each piece does

| Command / snippet | Purpose |
|---|---|
| `git --no-pager log --oneline -N -- <path>` | List last *N* commits touching a path, one line each, no pager. |
| `git --no-pager show <sha> -- <path>` | Show a single commit's diff for one path (used to see the dependency swap). |
| `mvn -pl <module> dependency:tree` | Print the resolved dependency graph for one module (find what gets shaded). |
| `mvn -pl <module> dependency:build-classpath -Dmdep.outputFile=<f>` | Write the resolved runtime classpath to a file for per-jar size analysis. |
| `mvn -pl <module> package [-DskipTests]` | Build the shaded fat-jar (the Lambda artifact); omit `-DskipTests` to also run the 93 unit tests. |
| `[System.IO.Compression.ZipFile]::OpenRead(...).Entries \| Measure-Object Length -Sum` | Sum uncompressed entry sizes = the **unzipped** size Lambda enforces. |
| `git checkout -b <branch>` | Create + switch to the feature branch off `develop`. |
| `git add <files>` / `git commit -m "..."` | Stage and record the change (message includes `ION-16417`). |
| `git push --set-upstream origin <branch>` | First push; creates the remote branch and sets upstream tracking. |
| `git push` | Subsequent pushes once upstream is set. |
| `git rev-parse --abbrev-ref --symbolic-full-name '@{u}'` | Print the tracked upstream branch (verify the push target). |
