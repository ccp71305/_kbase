# value-added-service — AWS SDK 2.x (cloud-sdk) + OWASP Upgrade — Work Log (ION-16110)

**Branch:** `feature/ION-16110-vas-owasp-aws-upgrade` (from latest `develop` @ `291dfb59`)
**Model:** Claude Opus 4.8 (1M context)
**Not pushed** — for local review.
**Companion design:** `2026-07-24-vas-owasp-aws-upgrade-design.md`.

## 1. Summary

- Goal: resolve OWASP HIGH CVEs (commons `1.0.28-SNAPSHOT` + Jackson `2.21.4`) and migrate all AWS interactions
  (DynamoDB + SNS) off AWS SDK v1 to the cloud-sdk (AWS SDK 2.x), fully backward-compatible with 1.x data.
- Delivered as a **single squashed commit** `dbdef03c03` referencing `ION-16110` (OWASP fix + full production
  cloud-sdk migration + DynamoDB-Local integration tests + unit coverage). The OWASP fix and the migration are
  inseparable: `commons 1.0.28` removes the legacy `com.inttra.mercury.messaging.*` package (no shim), so the bump
  cannot compile without the SNS migration; and clearing the AWS-SDK-v1 CVEs requires removing `dynamo-client` (the
  DynamoDB migration). See design doc §3.

## 2. Rebase

Not required. The feature branch did not previously exist; it was created fresh from the latest `develop`
(`291dfb596185223359b96056e4a31dea339cfc5b`). No `value-added-service` commits landed on `develop` in between.

## 3. OWASP dependency-check (pre / post)

Both scans target the shaded jar; reports copied to `C:\temp\latest-dep-chk-reports\vas\{baseline,post}`.

| Scan | Total | HIGH | MEDIUM |
|---|---|---|---|
| **Baseline** (develop, commons 1.R.01.023) | 25 | 6 | 19 |
| **Post** (commons 1.0.28 + jackson 2.21.4 + cloud-sdk) | 12 | **0** | 12 |

- HIGH resolved: jackson-databind `2.21.0`→`2.21.4` clears `CVE-2026-54512`/`CVE-2026-54513`; the http-component
  HIGHs `CVE-2026-54399`/`CVE-2026-54428` (httpcore5) were also cleared (httpcore5 upgraded to `5.4.3` via AWS SDK
  v2's apache-client). The prompt anticipated 2 http HIGH false positives would remain; in practice **0 HIGH remain**.
- Remaining 12 MEDIUM are framework-level and parent-pom managed (jetty `12.1.9` `CVE-2026-10051`, dropwizard
  `metrics-httpclient5` `CVE-2014-3577`/`CVE-2020-13956`, `commons-lang3 3.13.0` `CVE-2025-48924`, jackson-databind
  `2.21.4` `CVE-2026-54515` — fixable only by `2.21.5+`/`2.22.0`, left at `2.21.4` to match the booking reference).

## 4. Design plan

See `2026-07-24-vas-owasp-aws-upgrade-design.md` (dependency changes, per-attribute fidelity contract, class list,
testing strategy).

## 5. VS Code run configs

Added "Run/Debug Value Added Service" launch configs to `.vscode/launch.json` (mirroring the booking entries,
`mainClass=com.inttra.mercury.vas.ValueAddedServiceApp`, `args=server conf/int/config.yaml`). Note: `.vscode/` is
git-ignored repo-wide, so these are developer-local and not part of the commit.

## 6. Develop boot-check

App booted cleanly on the latest `develop` (unchanged) against `conf/int/config.yaml`:
`GET :8080/vas/services/ping` = 200, `GET :8081/admin/healthcheck` = healthy. Safe to proceed. (Prerequisite fix:
`~/.aws/credentials` had duplicate keys in one profile → de-duplicated after backup; `aws sso login` refreshed the
expired SSO session.)

## 7. Implementation

Full production migration (see design §6). Highlights:
- DynamoDB → cloud-sdk enhanced client: `DynamoDBValueAddedService` (`@Table`/`@DynamoDbBean`), nested `@DynamoDbBean`
  `Audit`, `CarrierResponseAttributeConverter`/`InttraResponseAttributeConverter` (ported `DynamoSupport`),
  `ValueAddedServiceDao` (injected `DatabaseRepository`, consistent-read partition query), `ValueAddedServiceDynamoModule`,
  `DynamoValueAddedServiceTableCommand` (cloud-sdk `DynamoDbAdminCommand`).
- SNS → cloud-sdk: `ValueAddedServiceMessagingModule` provides `NotificationService` + `EventPublisher`;
  `EventLogger`/`MetaData` re-pointed to `cloudsdk.notification.workflow.*` in both Hapag-Lloyd clients.
- Ported `dynamo-client` utilities into `com.inttra.mercury.vas.dynamodb.support` for byte-identical encoding.
- commons `1.0.28-SNAPSHOT`; `dynamo-client` + prod AWS SDK v1 removed; Jackson pinned to `2.21.4`.
- Backward compatibility proven by the integration test (§8). Migrated app boots cleanly (repository for
  `inttra_int_ValueAddedService`, `NotificationService`/`EventPublisher`, `EventLogger` all wired; ping/healthcheck 200).

## 8. Tests & coverage

**Passing test commands (all BUILD SUCCESS):**
- `mvn -pl value-added-service test` — unit tests.
- `mvn -pl value-added-service verify` — unit + DynamoDB-Local integration tests.
- `mvn -pl value-added-service -Pmercury-commons,sonar verify -Dsonar.skip=true` — with JaCoCo agents.

**Counts (JUnit 5 only; no TestNG):** unit **213**, integration **9** — total **222**, 0 failures, 0 errors, 0 skipped.

**JaCoCo union (unit + integration) line coverage of new/changed code:**

| Class | Coverage |
|---|---|
| `ValueAddedServiceDao` | 100% (24/24, IT) |
| `CarrierResponseAttributeConverter` | 100% (8/8) |
| `InttraResponseAttributeConverter` | 100% (8/8) |
| `support/GZip` | 100% (17/17) |
| `support/DynamoSupportException` | 100% (8/8) |
| `support/DynamoSupport` | 88% (50/57) |
| `ValueAddedServiceMessagingModule` | 90% (19/21) |
| `DynamoValueAddedServiceTableCommand` | 100% (12/12) |
| `ValueAddedServiceDynamoModule` | 89% (25/28) |
| `model/DynamoDBValueAddedService`, `model/Audit` | excluded via `sonar.coverage.exclusions=**/model/**` (functionally covered by IT) |

The remaining uncovered lines are unreachable defensive guards (e.g. the `@Table`-annotation-missing check on an
entity that always carries `@Table`) and a `configure()` log line. AWS-SDK client-construction paths are exercised
offline in unit tests by supplying dummy static credentials via system properties (no network call). JaCoCo report:
`value-added-service/target/site/jacoco`.

## 9. cloud-sdk gaps

- **Generic-`Object` / class-name-tagged string encoding.** cloud-sdk has no converter equivalent to the
  `dynamo-client` `DynamoSupport` custom format (`<fqcn>:<json>` with optional gzip+base64). Workaround: ported
  `DynamoSupport`/`GZip` into the module. **Proposed enhancement:** add a reusable
  `cloud-sdk-aws` `JsonClassTaggedAttributeConverter<T>` (with the size-threshold gzip behaviour) so modules that stored
  polymorphic payloads with the legacy format can migrate without vendoring the utility.
- No other gaps: `DateEpochSecondAttributeConverter` and `OffsetDateTimeTypeConverter` matched the legacy encodings
  exactly, and `DynamoDbAdminCommand` covered the annotation-driven table/GSI/TTL bootstrap.

## 10. Command log (key commands, with intent)

```powershell
# Orientation / branch
git fetch origin; git checkout develop; git rev-parse HEAD           # latest develop 291dfb59 baseline
git checkout -b feature/ION-16110-vas-owasp-aws-upgrade develop      # create feature branch (branch did not exist)

# Prerequisite AWS auth (boot-check needs Parameter Store)
aws sso login --sso-session INTTRA-Dev-Engg                          # refresh expired SSO
aws sts get-caller-identity                                          # account 081020446316 (INT)
aws dynamodb list-tables --query "TableNames[?contains(@,'ValueAddedService')]"  # -> inttra_int_ValueAddedService (verify prefix)

# Boot-check (develop, then migrated)
mvn -q -pl value-added-service -am package -DskipTests               # shaded jar
java -jar target/value-added-service-1.0.jar server conf/int/config.yaml  # ping/healthcheck 200

# OWASP baseline + post
dependency-check --project value-added-service-baseline --scan <jar> --out owasp-baseline --suppression suppressions.xml --nvdApiKey $NVD  # 25 vulns / 6 HIGH
dependency-check --project value-added-service-post     --scan <jar> --out owasp-post     --suppression suppressions.xml --nvdApiKey $NVD  # 12 vulns / 0 HIGH

# Reference/impact analysis (why: find AWS footprint + reference impls)
grep "com.amazonaws|messaging|dynamo|SNS|EventPublisher" value-added-service/src   # confirmed DynamoDB + SNS footprint
kb/glob over booking, webbl, mercury-services-commons                # cloud-sdk patterns + converter formats
jar tf commons-1.0.28-SNAPSHOT.jar | grep messaging                  # confirmed messaging.* removed in 1.0.28

# Build / test / coverage
mvn -pl value-added-service test                                     # 209 unit tests
mvn -pl value-added-service verify                                   # 209 unit + 7 DynamoDB-Local IT
mvn -pl value-added-service "-Pmercury-commons,sonar" verify "-Dsonar.skip=true"  # + JaCoCo
```

(Full per-command output and findings are recorded in the mcp-context session `078302148c5345a0`.)

## 11. Build / packaging results

`mvn -pl value-added-service verify` = **BUILD SUCCESS**. Shaded jar `value-added-service-1.0.jar` (~108 MB) contains
AWS SDK v2 (`2.30.24`) + `jackson-databind 2.21.4`; AWS SDK v1 `1.12.730` remains only transitively via
`cloud-sdk-aws`'s SQS extended client (same as booking) and is not flagged by dependency-check.

## 12. Token-usage

Token-usage telemetry is captured automatically by the mcp-context harness hooks (no manual `session_record_usage`
call, since the model cannot see its own usage block). See `session_usage_report` for session `078302148c5345a0`.

## 13. References

- Jira: ION-16110.
- Reference modules: `booking`, `webbl`, `network`, `auth`, `registration`.
- Reference docs: `value-added-service/docs/2026-06-30-value-added-service-aws2x-DESIGN-claude.md`,
  `booking/docs/2026-06-01-booking-aws2x-upgrade-desing-impl-review-claude.md`,
  `visibility/docs/2026-06-01-visibility-aws-upgrade-design-impl-review-claude.md`.

## 14. Live DynamoDB table verification (all environments)

Live tables described with the AWS CLI: INT via profile `081020446316_INTTRA-Dev-Engg`; QA/CVT/PROD (all in AWS
account `642960533737`) via a static-credential profile for `INTTRA2-QATeam`.

| Env | Table | Partition key | Attr defs | GSI (`valueAddedServiceBookingNumber-index`) | Throughput | TTL | Items |
|---|---|---|---|---|---|---|---|
| INT  | `inttra_int_ValueAddedService`  | `id` (S) HASH | `id` (S), `bookingNumber` (S) | `bookingNumber` (S) HASH, **KEYS_ONLY**, 5/5, ACTIVE | 5/5 PROVISIONED | **ENABLED** on `expiresOn` | 0 |
| QA   | `inttra2_qa_ValueAddedService`  | `id` (S) HASH | `id` (S), `bookingNumber` (S) | `bookingNumber` (S) HASH, **KEYS_ONLY**, 5/5, ACTIVE | 5/5 PROVISIONED | DISABLED | 50,004 |
| CVT  | `inttra2_cvt_ValueAddedService` | `id` (S) HASH | `id` (S), `bookingNumber` (S) | `bookingNumber` (S) HASH, **KEYS_ONLY**, 5/5, ACTIVE | 5/5 PROVISIONED | DISABLED | 264 |
| PROD | `inttra2_prod_ValueAddedService`| `id` (S) HASH | `id` (S), `bookingNumber` (S) | `bookingNumber` (S) HASH, **KEYS_ONLY**, 5/5, ACTIVE | 5/5 PROVISIONED | DISABLED | 1,236,915 |

## 15. Entity annotations vs live tables + admin-command idempotency

### 15.1 Structural match (no discrepancies)

The `DynamoDBValueAddedService` entity annotations match the live table structure in **all four** environments:

| Live table property | Entity annotation | Match |
|---|---|---|
| table name `<env>_ValueAddedService` | `@Table(name = "ValueAddedService")` + `BaseDynamoDbConfig.environment` → `tablePrefix = environment + "_"` | ✅ |
| partition key `id` (S) | `@DynamoDbPartitionKey @DynamoDbAttribute("id")` on `String getHashKey()` | ✅ |
| GSI `valueAddedServiceBookingNumber-index`, key `bookingNumber` (S), projection **KEYS_ONLY** | `@DynamoDbSecondaryPartitionKey(indexNames = BOOKING_NUMBER_INDEX)` + `@GsiConfig(indexName = BOOKING_NUMBER_INDEX, projection = ProjectionType.KEYS_ONLY)` on `String getBookingNumber()` | ✅ |
| provisioned throughput 5/5 | `readCapacityUnits: 5` / `writeCapacityUnits: 5` in each `config.yaml` `dynamoDbConfig` | ✅ |

### 15.2 Build / command invocation — tables & GSI treated as existing, nothing overridden

The table-admin command (`DynamoValueAddedServiceTableCommand extends DynamoDbAdminCommand`) is a **separate
Dropwizard `dynamo-create` command**. It is **not** executed on `server` startup — normal boot registers nothing.

When `dynamo-create` *is* run explicitly, its behaviour against the existing tables is idempotent (verified in the
cloud-sdk-aws sources `DynamoDbAdminCommand` / `DynamoDbAdminUtil`):

1. `describeTable(tableName)` succeeds → logs `Table already exists` → **no** `CreateTable`, so key schema, attribute
   definitions and provisioned throughput of the existing table are **left untouched**.
2. For the GSI it calls `DynamoDbAdminUtil.addGlobalSecondaryIndexIfNotExists(...)`, which describes the table, finds
   the index by name (`indexName().equals("valueAddedServiceBookingNumber-index")`) and **returns immediately** →
   the existing KEYS_ONLY GSI is **not** modified.
3. TTL is only touched when the entity declares `@TTL`; **our entity does not**, so `metadata.getTtlAttributeName()`
   is empty and `updateTimeToLive` is **never** called — INT's ENABLED TTL and QA/CVT/PROD's DISABLED TTL are both
   preserved. (And even when called, `enableTimeToLive` is a no-op if TTL is already enabled.)
4. Streams are only touched with a `@Stream` annotation (absent) — **not** modified.

**Conclusion:** on both `server` startup and an explicit `dynamo-create`, the table and GSI are registered as
**existing** and **nothing is overridden**.

### 15.3 Flagged discrepancy — TTL is inconsistent across environments

- **INT** has native TTL **ENABLED** on `expiresOn`; **QA/CVT/PROD** have TTL **DISABLED**.
- This is a pre-existing **environment inconsistency** in the live tables, independent of this change.
- The application writes `expiresOn` identically in every environment — an epoch-seconds Number via
  `DateEpochSecondAttributeConverter` — which is exactly the format native TTL consumes. So behaviour is correct
  whether or not TTL is enabled; TTL is a table-level setting, not an on-wire format change.
- **Decision (confirmed with the team):** because the higher environments (QA/CVT/PROD) do **not** use native TTL,
  the entity intentionally does **not** declare `@TTL`. The admin command therefore never enables/disables TTL, so the
  existing per-environment TTL state is preserved and never overridden. No code change required.
- The earlier design doc (`2026-06-30-…`) stated "no TTL is configured on the table today"; that assumption was
  partially incorrect (INT has it enabled). This section supersedes it.

## 16. Command log — DynamoDB verification & finalisation

```powershell
# Add QA static credentials to a dedicated static-only profile (config-file profile uses SSO which had expired);
# a distinct profile name avoids the config sso_session overriding the static keys. (Local ~/.aws only; never committed.)
#   -> [qa-team-static] added to ~/.aws/credentials
aws sts get-caller-identity --profile qa-team-static            # verify -> account 642960533737 (INTTRA2 / QA)

# Describe each live table + its TTL (schema/GSI/throughput/TTL capture for §14)
aws dynamodb describe-table       --table-name inttra_int_ValueAddedService   --profile 081020446316_INTTRA-Dev-Engg
aws dynamodb describe-time-to-live --table-name inttra_int_ValueAddedService   --profile 081020446316_INTTRA-Dev-Engg
aws dynamodb describe-table       --table-name inttra2_qa_ValueAddedService   --profile qa-team-static
aws dynamodb describe-time-to-live --table-name inttra2_qa_ValueAddedService   --profile qa-team-static
aws dynamodb describe-table       --table-name inttra2_cvt_ValueAddedService  --profile qa-team-static
aws dynamodb describe-time-to-live --table-name inttra2_cvt_ValueAddedService  --profile qa-team-static
aws dynamodb describe-table       --table-name inttra2_prod_ValueAddedService --profile qa-team-static
aws dynamodb describe-time-to-live --table-name inttra2_prod_ValueAddedService --profile qa-team-static

# Coverage top-up for the Guice modules + table-admin command (offline AWS client construction via dummy creds)
mvn -pl value-added-service test "-Dtest=ValueAddedServiceMessagingModuleTest,ValueAddedServiceDynamoModuleTest,DynamoValueAddedServiceTableCommandTest"
mvn -pl value-added-service "-Pmercury-commons,sonar" verify "-Dsonar.skip=true"   # 213 unit + 7 IT + JaCoCo

# Final single-commit assembly
git reset --soft develop                                        # collapse the two commits, keep all changes staged
git commit -m "ION-16110: value-added-service OWASP dependency-check + AWS SDK 2.x (cloud-sdk) upgrade" # -> dbdef03c03
mvn -pl value-added-service clean verify                        # final certify: BUILD SUCCESS, 213 unit + 7 IT
```

> Source references reviewed for §15.2: `cloud-sdk-aws` `DynamoDbAdminCommand.createTableWithGsisIfNotExists`
> (describe-then-skip; TTL only via `@TTL`) and `DynamoDbAdminUtil.addGlobalSecondaryIndexIfNotExists` /
> `enableTimeToLive` (both no-op when the index/TTL already exist).

## 17. PR review fixes (PR #1119)

**Persistence bug — optional (null) response payloads.** The reviewer flagged that
`CarrierResponseAttributeConverter` / `InttraResponseAttributeConverter` `transformFrom` always built an
`AttributeValue` (`AttributeValue.builder().s(dynamoSupport.objectToString(input)).build()`). When `carrierResponse`
or `inttraResponse` is null, `objectToString` returns null and the resulting `AttributeValue` has no data type set, so
DynamoDB rejects the put/update with `ValidationException: Supplied AttributeValue is empty`. Any DAO `save` with an
absent carrier/INTTRA payload (allowed by the method signature) would fail — a regression vs the v1 mapper, which
omitted null attributes.

- **Fix:** both converters now return `null` for a null input (`if (input == null) return null;`), so the enhanced
  client omits the attribute — matching the legacy behaviour. Real payloads are still encoded via `DynamoSupport`
  (unchanged, byte-identical).
- **Tests:** added `ValueAddedServiceDaoIT.OptionalPayloads` — (1) `save(actor, scac, null, inttraResponse)` persists
  and omits `carrierResponse`; (2) an entity with both `carrierResponse` and `inttraResponse` null persists and omits
  both — each asserting the raw item does not contain the attribute and the round-tripped entity reads them back as
  null. Updated the two converter unit tests' null cases to assert `transformFrom(null)` returns `null`.
- **Result:** `mvn -pl value-added-service verify` = BUILD SUCCESS — **213 unit + 9 integration** tests (was 7),
  0 failures. No `ValidationException` on null-payload saves.

## 18. Command log — 2026-07-28 (PR-review fix, rebase, troubleshooting)

### 18.1 Resume & stale-process troubleshooting

Yesterday a `mvn verify` run hung (machine slowness). On resume, the goal was to find any leftover build/test JVM
from that run and confirm it was safe to ignore — **without** killing the wrong process (e.g. the editor's own JVM).

```powershell
# 1) List any Java/Maven processes still running, with CPU time (a hung build JVM shows high accumulated CPU).
Get-Process -Name java,mvn -ErrorAction SilentlyContinue | Select-Object Id,ProcessName,CPU | Format-Table -AutoSize
#   -> found ONE java process: PID 23676, CPU ~169s. One process (not the mvn+forked-test pair a live build shows),
#      which hinted the hung Maven/DynamoDB-Local JVM had already exited and this was something else.

# 2) Check whether the app's own ports are held (VAS binds 8080/8081). Empty result => not our service.
Get-NetTCPConnection -State Listen -LocalPort 8080,8081 -ErrorAction SilentlyContinue | Select-Object LocalPort,OwningProcess
#   -> no listeners => the leftover java is NOT a running VAS/Dropwizard server.

# 3) IDENTIFY the process by its full command line before touching it. This is the decisive step:
#    Win32_Process.CommandLine reveals exactly what a PID is, so you never kill blindly by name.
(Get-CimInstance Win32_Process -Filter "ProcessId=23676").CommandLine
#   -> "c:\Users\...\.vscode\extensions\redhat.java-1.55.0-.../jre/21.0.11/bin/java ...
#       -Declipse.application=org.eclipse.jdt.ls.core.id1 ... org.eclipse.jdt.ls.core.product ..."
#      The path (.vscode\extensions\redhat.java) + the eclipse.jdt.ls flags => this is the VS Code Java
#      LANGUAGE SERVER (redhat.java extension), NOT a Maven/Surefire/Failsafe JVM. Left it running.
```

**How the determination was made (reusable checklist):**
- **Count & shape:** a live Maven test run shows the `mvn` launcher **plus** a forked Surefire/Failsafe JVM. A single
  lingering `java` with no `mvn` parent suggests the build already died.
- **Ports:** our service uses 8080/8081; a hung *server* would still hold them. None held => not our app.
- **Command line is ground truth:** `Get-CimInstance Win32_Process -Filter "ProcessId=<pid>"` (or
  `Get-Process -Id <pid> | Select-Object Path`) exposes the jar/main-class/flags. Editor JVMs carry
  `.vscode\extensions\...` paths and `eclipse.jdt.ls` (Java LS) or `gradle`/`lombok` daemons; build JVMs carry
  `surefire`/`failsafe` booter jars or `-jar target\...`. Match on those tokens before acting.
- **Safety rule:** only ever stop a process by explicit **PID** after identifying it (`Stop-Process -Id <pid>`),
  never by name.

```powershell
# Confirm the working tree still had yesterday's uncommitted fix (5 files), and branch is at the pushed commit.
git --no-pager status -sb
git --no-pager status --short -- value-added-service
git --no-pager log --oneline -1
```

### 18.2 Verify the null-payload fix (unit + DynamoDB-Local IT)

```powershell
# Run the full module verify, but LOG to a file (Tee-Object) instead of piping straight into Select-String.
# Lesson from yesterday: piping mvn through Select-String buffers everything and shows nothing until the JVM exits,
# which looks like a hang. Logging to a file lets you inspect partial output while it runs.
mvn -pl value-added-service verify 2>&1 | Tee-Object -FilePath "$env:TEMP\vas-fixverify.log"

# Then extract just the signal from the log:
Select-String -Path "$env:TEMP\vas-fixverify.log" -Pattern "Tests run:.*Failures" | ForEach-Object { $_.Line }
Select-String -Path "$env:TEMP\vas-fixverify.log" -Pattern "OptionalPayloads|ValidationException|AttributeValue is empty"
Select-String -Path "$env:TEMP\vas-fixverify.log" -Pattern "BUILD SUCCESS|BUILD FAILURE"
#   -> BUILD SUCCESS; ValueAddedServiceDaoIT$OptionalPayloads 2 tests pass; 213 unit + 9 IT; no ValidationException.
```

### 18.3 Rebase onto latest develop, keep one clean commit, force-push

```powershell
# See what landed on develop since our branch base, and whether any of it touches our module (conflict risk).
git fetch origin
git --no-pager log --oneline HEAD..origin/develop            # 21 new commits on develop
git rev-list --count HEAD..origin/develop                    # -> 21
git --no-pager log --oneline HEAD..origin/develop -- value-added-service/   # -> EMPTY => no conflict in our module

# Safety net BEFORE rewriting history: a throwaway backup branch + tag at the current tip.
git branch -f feature/ION-16110-vas-owasp-aws-upgrade-backup-20260728 HEAD
git tag -f ION-16110-pre-rebase-20260728 HEAD

# Fold the review fix into the single existing commit, then rebase that one commit onto the latest develop.
git commit --amend --no-edit                                 # amend staged fix -> e900328527
git rebase origin/develop                                    # clean, no conflicts -> new tip 1a41ba881e

# Verify exactly one outgoing commit sitting on top of the current develop tip.
git rev-list --count origin/develop..HEAD                    # -> 1
git merge-base --is-ancestor origin/develop HEAD             # exit 0 => HEAD is on top of develop tip 8dad1d555c

# Re-certify on the rebased base (new develop deps) before publishing.
mvn -pl value-added-service clean verify                     # BUILD SUCCESS: 213 unit + 9 IT

# Publish the rewritten single commit safely: --force-with-lease aborts if someone else pushed the branch meanwhile.
git push --force-with-lease origin feature/ION-16110-vas-owasp-aws-upgrade

# Confirm local and remote are identical (0 ahead / 0 behind) and still one commit above develop.
git fetch origin
git --no-pager rev-list --left-right --count origin/feature/ION-16110-vas-owasp-aws-upgrade...HEAD   # -> 0   0
git rev-list --count origin/develop..HEAD                    # -> 1
```

**Outcome:** single clean commit `1a41ba881e` on top of the latest `develop` (`8dad1d555c`), fully in sync with the
remote PR branch #1119, all tests green. Backup retained at branch `...-backup-20260728` / tag
`ION-16110-pre-rebase-20260728`.

## 19. Running the application — VS Code run config & terminal equivalent

### 19.1 VS Code run configs

Added to `.vscode/launch.json` (repo root). Note: `.vscode/` is git-ignored repo-wide, so these are developer-local
and are **not** part of the commit — they mirror the existing booking entries.

```json
{
    "type": "java",
    "name": "Run Value Added Service",
    "request": "launch",
    "mainClass": "com.inttra.mercury.vas.ValueAddedServiceApp",
    "projectName": "value-added-service",
    "args": "server ${workspaceFolder}/value-added-service/conf/int/config.yaml",
    "cwd": "${workspaceFolder}/value-added-service",
    "console": "integratedTerminal"
},
{
    "type": "java",
    "name": "Debug Value Added Service",
    "request": "launch",
    "mainClass": "com.inttra.mercury.vas.ValueAddedServiceApp",
    "projectName": "value-added-service",
    "args": "server ${workspaceFolder}/value-added-service/conf/int/config.yaml",
    "cwd": "${workspaceFolder}/value-added-service",
    "console": "integratedTerminal",
    "vmArgs": "-Xmx2g -Xms512m"
}
```

In VS Code: open **Run and Debug** (Ctrl+Shift+D), pick **Run Value Added Service** (or **Debug …** for breakpoints).

### 19.2 Terminal equivalent (same main class, args, cwd)

The int `config.yaml` resolves `${awsps:...}` from AWS Parameter Store at startup, so a valid AWS session for the INT
account (`081020446316`) is required first.

```powershell
# 0) Ensure a valid AWS session for INT (the default profile targets account 081020446316).
aws sts get-caller-identity            # if the SSO token expired: aws sso login --sso-session INTTRA-Dev-Engg

# 1) Build the shaded jar (skip if target\value-added-service-1.0.jar is already current).
mvn -pl value-added-service -am package -DskipTests

# 2) Run exactly like the "Run Value Added Service" launch config:
#    mainClass = com.inttra.mercury.vas.ValueAddedServiceApp | args = server conf\int\config.yaml | cwd = value-added-service
cd value-added-service
$env:AWS_PROFILE = "default"
java -cp target\value-added-service-1.0.jar com.inttra.mercury.vas.ValueAddedServiceApp server conf\int\config.yaml
#    (equivalent, since the jar's manifest Main-Class is ValueAddedServiceApp:)
#    java -jar target\value-added-service-1.0.jar server conf\int\config.yaml
```

### 19.3 Verify it is up, then stop it

```powershell
# App connector 8080, admin connector 8081.
(Invoke-WebRequest -UseBasicParsing http://localhost:8080/vas/services/ping).Content        # {"healthy":"true"}
(Invoke-WebRequest -UseBasicParsing http://localhost:8081/admin/healthcheck).StatusCode      # 200
Get-NetTCPConnection -State Listen -LocalPort 8080,8081 | Select-Object LocalPort,OwningProcess

# Stop by the exact PID that owns the app port (identify first, then stop by -Id — never by name).
$pid8080 = (Get-NetTCPConnection -State Listen -LocalPort 8080).OwningProcess
Stop-Process -Id $pid8080 -Force
```

**Verified runs (2026-07-28):** started twice from the terminal against `conf/int/config.yaml`. Both times all AWS
services booted cleanly — `ValueAddedServiceDynamoModule` created the DynamoDB repository for
`inttra_int_ValueAddedService` (region `us-east-1` via `DefaultAwsRegionProviderChain`, `DefaultCredentialsProvider`),
`ValueAddedServiceMessagingModule` created the SNS `NotificationService` + `EventPublisher` for
`arn:aws:sns:us-east-1:081020446316:inttra_int_sns_event`, and the `EventLogger` was injected into the Hapag-Lloyd
clients — then `GET :8080/vas/services/ping` = `200 {"healthy":"true"}` and `GET :8081/admin/healthcheck` = 200 healthy.

## 20. ECS deployment verification + `dynamo-create` command-name analysis (2026-07-28)

### 20.1 INT ECS deployment health (VAS-dev on cluster ANEINWEBSVC-001)

Deployment coordinates taken from the Jenkins console (artifact `centos:VAS-26.07.001`, task def
`VAS-latest-dev-Task.json`): cluster `ANEINWEBSVC-001`, service `VAS-dev`, container `VAS-dev-Container:8080`,
target group `tg-int-vas-inttra`. Verified via the AWS CLI with profile `081020446316_INTTRA-Dev-Engg`.

| Check | Result |
|---|---|
| Service `VAS-dev` | ACTIVE — desired 1 / running 1 / pending 0, launchType EC2 |
| Deployment | single PRIMARY, rolloutState COMPLETED, reached **steady state** 08:44 (fresh deploy) |
| Task `7da2e1f2…` | RUNNING, image `081020446316.dkr.ecr.us-east-1.amazonaws.com/centos:VAS-dev`, no exitCode; ECS health `UNKNOWN` (task def has `healthCheck: null` — expected, not a failure) |
| App boot (CloudWatch `inttra-ecs-logs`) | `ValueAddedServiceDynamoModule` → repo for `inttra_int_ValueAddedService`; `ValueAddedServiceMessagingModule` → SNS `NotificationService` + `EventPublisher` for `inttra_int_sns_event`; `Starting InttraServer`; **0 ERROR/Exception** in startup |
| ALB health | `ELB-HealthChecker/2.0 GET /vas/services/ping → 200` continuously → target healthy |

The deployed container boots the **same cloud-sdk stack** as local. (`elbv2:DescribeTargetHealth` returned AccessDenied
on the SSO role — a permissions gap, not a health problem; the continuous ELB 200s + ECS steady state prove the
target is healthy.)

```powershell
# Login + identity
aws sso login --profile 081020446316_INTTRA-Dev-Engg
aws sts get-caller-identity --profile 081020446316_INTTRA-Dev-Engg          # account 081020446316 (INT)

# Service status + deployment rollout + recent events
aws ecs describe-services --cluster ANEINWEBSVC-001 --services VAS-dev --profile 081020446316_INTTRA-Dev-Engg --region us-east-1 `
  --query "services[0].{status:status,desired:desiredCount,running:runningCount,pending:pendingCount,taskDef:taskDefinition,deployments:deployments[].{rollout:rolloutState,status:status}}"
aws ecs describe-services --cluster ANEINWEBSVC-001 --services VAS-dev --profile 081020446316_INTTRA-Dev-Engg --region us-east-1 `
  --query "services[0].events[0:5].[createdAt,message]" --output text

# Running task detail + image + container status
aws ecs list-tasks   --cluster ANEINWEBSVC-001 --service-name VAS-dev --profile 081020446316_INTTRA-Dev-Engg --region us-east-1 --query "taskArns[0]" --output text
aws ecs describe-tasks --cluster ANEINWEBSVC-001 --tasks <taskArn> --profile 081020446316_INTTRA-Dev-Engg --region us-east-1 `
  --query "tasks[0].{lastStatus:lastStatus,health:healthStatus,image:containers[0].image,exitCode:containers[0].exitCode}"

# Task-def log config (awslogs group/prefix + container command + healthCheck)
aws ecs describe-task-definition --task-definition VAS-latest-dev-Task:1 --profile 081020446316_INTTRA-Dev-Engg --region us-east-1 `
  --query "taskDefinition.containerDefinitions[0].{logDriver:logConfiguration.logDriver,options:logConfiguration.options,command:command,healthCheck:healthCheck}"
#   -> command = ["/app/run.sh"] (execs: java ... server ./config.yaml) ; healthCheck = null ; awslogs-group inttra-ecs-logs, prefix VAS-latest-dev

# Deployed container startup logs (confirm the cloud-sdk AWS wiring booted + ELB 200s)
aws logs get-log-events --log-group-name inttra-ecs-logs `
  --log-stream-name "VAS-latest-dev/VAS-dev-Container/<taskId>" --profile 081020446316_INTTRA-Dev-Engg --region us-east-1 --start-from-head --limit 200 --query "events[].message" --output text
```

### 20.2 How the pre-upgrade `dynamo-create` worked with the deprecated dynamo-client

The **running** container executes `/app/run.sh` → `java ... server ./config.yaml`, i.e. the Dropwizard **`server`**
command. It does **not** run `dynamo-create` on boot. `dynamo-create` is a **separate one-off provisioning command**
invoked by a deploy/pipeline step, not by the service at runtime.

Pre-upgrade wiring (verified from `origin/develop` + `dynamo-client` sources):
- `DynamoValueAddedServiceTableCommand extends AbstractDynamoCommand` (from `dynamo-client`), which
  `extends ConfiguredCommand` and its **only** constructor calls `super("dynamo-create", "Create dynamo tables.")` —
  that registers the CLI verb. The app added it via `.command(new DynamoValueAddedServiceTableCommand())`.
- On invocation it built a **v1** `AmazonDynamoDB` (`AmazonDynamoDBClientBuilder.standard()...`), wrapped in a
  `DynamoDBMapper` with a table-name **prefix** from `environment`, then `createTableAndWaitUntilActive(...)` derived
  the schema from `dynamoDBMapper.generateCreateTableRequest(clazz)` using the **v1 annotations** (`@DynamoDBTable`,
  `@DynamoDBHashKey`, `@DynamoDBIndexHashKey`) and the YAML `dynamoDbTableConfig` throughput/GSI block.
- "Deprecated" here means *slated for migration*, not JDK-`@Deprecated`/removed — `dynamo-client 1.R.01.023` was still
  a declared dependency, so `AbstractDynamoCommand` + `DynamoDBMapper` were fully on the classpath and functional. And
  since the tables already exist in every env, the step is effectively idempotent; the running container only ever
  executes `server`, so the legacy command never affected the live service.

Post-upgrade: same `dynamo-create` verb, but `DynamoValueAddedServiceTableCommand extends DynamoDbAdminCommand`
(cloud-sdk). It derives the schema from the **v2** annotations (`@DynamoDbBean`/`@Table`/`@GsiConfig`/
`@DynamoDbSecondaryPartitionKey`), reads throughput from `BaseDynamoDbConfig`, and is idempotent (describe-then-skip;
nothing overridden — see §15.2).

### 20.3 CI `$task` argument = the Dropwizard command name — cross-module comparison

The CI helper `mercury-run-docker-task.sh <task>` runs `java -jar <app>.jar <task> <config>.yaml`; the `<task>` token
is the **Dropwizard command name** registered via `super("<name>", ...)`, so **CI must pass exactly that name** or the
launch fails with an unknown-command error. Whether a module needs its CI `$task` updated during the cloud-sdk upgrade
depends entirely on whether its command name changed.

> **Correction (2026-07-28):** an earlier draft of this table listed visibility's old command as
> `DynamoContainerEventsTableCommand` (`dynamo-create`, no change). That was the wrong class. Visibility's actual deploy
> provisioning command was a **bespoke `CreateTables`** registered as **`create-tables`** — so visibility's `$task`
> **did** have to change to `dynamo-create`. `booking-bridge` was in the same situation. Both are corrected below.

| Module | OLD command class / base | OLD registered name | NEW command class / base | NEW registered name | CI `$task` change? |
|---|---|---|---|---|---|
| **value-added-service** | `DynamoValueAddedServiceTableCommand` → `AbstractDynamoCommand` (dynamo-client), `super()` | `dynamo-create` | `DynamoValueAddedServiceTableCommand` → `DynamoDbAdminCommand` (cloud-sdk), `super(ENTITY_CLASSES)` | `dynamo-create` | **NO — unchanged** |
| **visibility** (inbound) | `CreateTables` → `ConfiguredCommand`, `super("create-tables", "Create all tables for Container Events")` | **`create-tables`** | `VisibilityInboundDynamoDbAdminCommand` → `DynamoDbAdminCommand`, `super(ENTITY_CLASSES)` | **`dynamo-create`** | **YES — `create-tables` → `dynamo-create`** |
| **booking** | `CreateTables` → `ConfiguredCommand`, `super("create-tables", "Create all of the booking DynamoDB tables")` | **`create-tables`** | `BookingDynamoDbAdminCommand` → `DynamoDbAdminCommand` | **`dynamo-create`** | **YES — `create-tables` → `dynamo-create`** |
| **booking-bridge** | `CreateTables` → `ConfiguredCommand`, `super("create-tables", "Create the booking-bridge DynamoDB tables")` | **`create-tables`** | `CreateTables` → `DynamoDbAdminCommand`, `super(ENTITY_CLASSES)` (class kept the name, base changed) | **`dynamo-create`** | **YES — `create-tables` → `dynamo-create`** |

- The new cloud-sdk `DynamoDbAdminCommand` hardcodes `super("dynamo-create", ...)` and none of the subclasses
  (VAS, visibility, booking, booking-bridge) override that name — so **every migrated module's provisioning command is
  `dynamo-create`**.
- **value-added-service** already used `dynamo-create` before the upgrade, because its pre-upgrade
  `DynamoValueAddedServiceTableCommand` extended dynamo-client's `AbstractDynamoCommand`, whose only constructor is
  `super("dynamo-create", "Create dynamo tables.")`. So VAS is the exception — its command name did **not** change.
- **visibility, booking, and booking-bridge** each had a **bespoke `CreateTables extends ConfiguredCommand`**
  registered as **`create-tables`** (a hand-written provisioning command, not the dynamo-client base). Migrating them to
  the standardized `DynamoDbAdminCommand` renamed the verb to `dynamo-create`, so **their** deploy/CI `$task` had to be
  updated from `create-tables` → `dynamo-create` — matching the pattern you flagged. (booking-bridge kept the class
  *name* `CreateTables` but changed its base to `DynamoDbAdminCommand`, so the registered command name still changed.)
- `create-tables` also survives as a genuine command name in **`partner-integrator/pi-bl-in-processor`**
  (`CreateTables`, `super("create-tables", ...)`), which was not part of this cloud-sdk migration.

**Conclusion for value-added-service:** the Dropwizard command name is `dynamo-create` **both before and after** this
upgrade (unlike visibility / booking / booking-bridge, which moved from a bespoke `create-tables`). So the VAS deploy/CI
`$task` argument does **not** need to change. Action item: confirm the VAS Jenkins provisioning step (in
`jenkins-config`, outside this repo) passes `dynamo-create` — it already did, since the pre-upgrade command registered
the same name — so no code or pipeline change is required for VAS on this point.

```powershell
# Commands used for this analysis
# OLD VAS: extends dynamo-client AbstractDynamoCommand, super() -> inherits "dynamo-create"
git --no-pager show origin/develop:value-added-service/src/main/java/com/inttra/mercury/vas/config/DynamoValueAddedServiceTableCommand.java
# Base-class command names:
#   cloud-sdk   DynamoDbAdminCommand -> super("dynamo-create", "Manage DynamoDB tables and indexes from entity/domain classes.")
#   dynamo-client AbstractDynamoCommand -> super("dynamo-create", "Create dynamo tables.")

# Find every bespoke CreateTables ever committed in the migrated modules, then read each one's registered name.
git --no-pager log --all --pretty=format: --name-only | Select-String "(visibility|booking|booking-bridge)/.*CreateTables\.java" | Sort-Object -Unique
#   visibility(-inbound)/.../config/CreateTables.java  -> super("create-tables", "Create all tables for Container Events")
#   booking/.../dao/CreateTables.java                  -> super("create-tables", "Create all of the booking DynamoDB tables")
#   booking-bridge/.../dynamo/CreateTables.java        -> OLD super("create-tables", "Create the booking-bridge DynamoDB tables")
#                                                          NEW extends DynamoDbAdminCommand (super(ENTITY_CLASSES)) -> dynamo-create

# Read a specific old version by commit (deletion diff shows the removed super("create-tables",...) line):
git --no-pager show <commit>:visibility/visibility-inbound/src/main/java/com/inttra/mercury/visibility/inbound/config/CreateTables.java
git --no-pager show <oldestCommit>:booking-bridge/src/main/java/com/inttra/mercury/booking/bridge/dynamo/CreateTables.java

# Trace a file's OLD->NEW across the migration (first vs last commit touching it):
git --no-pager log --all --oneline -- booking-bridge/src/main/java/com/inttra/mercury/booking/bridge/dynamo/CreateTables.java
```

### 20.4 Exact command log used to verify the command-name findings (reproducible)

The precise commands run on 2026-07-28 to derive §20.3, each with the result observed. All are read-only history
queries (no working-tree changes).

```powershell
cd C:\Users\arijit.kundu\projects\mercury-services

# (1) Find the current/new dynamo-admin command classes in the reference modules.
Get-ChildItem -Recurse -File -Path booking,visibility -Filter "*.java" |
  Where-Object { $_.Name -match "Dynamo.*Command|.*TableCommand|.*AdminCommand" } | Select-Object FullName
#   -> booking/.../dynamodb/BookingDynamoDbAdminCommand.java
#      visibility/visibility-inbound/.../config/VisibilityInboundDynamoDbAdminCommand.java

# (2) New base + subclass command names (both inherit the hardcoded dynamo-create).
Select-String -Path "C:\Users\arijit.kundu\projects\mercury-services-commons\cloud-sdk-aws\src\main\java\com\inttra\mercury\cloudsdk\database\command\DynamoDbAdminCommand.java" -Pattern 'super\("'
#   -> super("dynamo-create", "Manage DynamoDB tables and indexes from entity/domain classes.")
Select-String -Path "booking\src\main\java\com\inttra\mercury\booking\dynamodb\BookingDynamoDbAdminCommand.java" -Pattern 'extends |super\('
Select-String -Path "visibility\visibility-inbound\src\main\java\com\inttra\mercury\visibility\inbound\config\VisibilityInboundDynamoDbAdminCommand.java" -Pattern 'extends |super\('
#   -> both: extends DynamoDbAdminCommand<...> ; super(ENTITY_CLASSES)

# (3) dynamo-client base command name (the pre-upgrade VAS + visibility inbound "table" command inherited it).
Select-String -Path "C:\Users\arijit.kundu\projects\mercury-services-commons\dynamo-client\src\main\java\com\inttra\mercury\dynamo\respository\command\AbstractDynamoCommand.java" -Pattern 'public AbstractDynamoCommand|super\("'
#   -> public AbstractDynamoCommand() { super("dynamo-create", "Create dynamo tables."); }   (only constructor)

# (4) OLD vs NEW value-added-service command (develop = pre-upgrade, working tree = post-upgrade).
git --no-pager show origin/develop:value-added-service/src/main/java/com/inttra/mercury/vas/config/DynamoValueAddedServiceTableCommand.java | Select-String 'extends |super\('
#   -> extends AbstractDynamoCommand<ValueAddedServiceConfig> ; super()            => dynamo-create (inherited)
Select-String -Path "value-added-service\src\main\java\com\inttra\mercury\vas\config\DynamoValueAddedServiceTableCommand.java" -Pattern 'extends |super\('
#   -> extends DynamoDbAdminCommand<ValueAddedServiceConfig> ; super(ENTITY_CLASSES) => dynamo-create (inherited)

# (5) Find EVERY bespoke CreateTables ever committed across the migrated modules (history, not just current tree).
git --no-pager log --all --pretty=format: --name-only |
  Where-Object { $_ -match "(visibility|booking|booking-bridge)/.*CreateTables.*\.java" } | Sort-Object -Unique
#   -> booking/src/main/java/.../athena/CreateTables.java
#      booking/src/main/java/.../dao/CreateTables.java
#      visibility/src/main/java/.../config/CreateTables.java
#      visibility/visibility-inbound/src/main/java/.../config/CreateTables.java
#      booking-bridge/src/main/java/.../dynamo/CreateTables.java

# (6) Read each bespoke CreateTables' registered name. If the file was later DELETED, its last commit is the
#     deletion commit, so read the removed ("-") lines from that commit's diff; otherwise show at the commit.
$vf = "visibility/visibility-inbound/src/main/java/com/inttra/mercury/visibility/inbound/config/CreateTables.java"
$vc = git --no-pager log --all --format="%H" -1 -- $vf                       # last (deletion) commit
git --no-pager show $vc -- $vf | Select-String -Pattern '^\-.*(class CreateTables|extends |super\(")'
#   -> -public class CreateTables extends ConfiguredCommand<VisibilityInboundApplicationConfig> {
#      -    super("create-tables", "Create all tables for Container Events");

# booking-bridge CreateTables still EXISTS (only its base changed) -> read oldest vs current.
$bb = "booking-bridge/src/main/java/com/inttra/mercury/booking/bridge/dynamo/CreateTables.java"
$oldest = git --no-pager log --all --format="%H" --reverse -- $bb | Select-Object -First 1
git --no-pager show "${oldest}:$bb" | Select-String 'class CreateTables|extends |super\("'
#   -> OLD: extends ConfiguredCommand<BookingBridgeConfig> ; super("create-tables", "Create the booking-bridge DynamoDB tables")
Select-String -Path $bb -Pattern 'class CreateTables|extends |super\('
#   -> NEW: extends DynamoDbAdminCommand<BookingBridgeConfig> ; super(ENTITY_CLASSES)  => dynamo-create
Select-String -Path "booking-bridge\src\main\java\com\inttra\mercury\booking\bridge\BookingBridgeApplication.java" -Pattern '\.command\('
#   -> .command(new CreateTables())

# booking dao/CreateTables registered name (via the PR that converted it to a Dropwizard command).
git --no-pager log --all --oneline -S 'extends AbstractDynamoCommand' -- "booking/**"
#   -> fa5b3ba8ed PR 460: convert CreateTables and DeleteTables to Dropwizard commands  (+ initial-stub commits)
$bf = "booking/src/main/java/com/inttra/mercury/booking/dao/CreateTables.java"
$bc = git --no-pager log --all --format="%H" -1 -- $bf
git --no-pager show $bc -- $bf | Select-String -Pattern '^\-.*(class CreateTables|extends |super\(")'
#   -> -public class CreateTables extends ConfiguredCommand<BookingConfig> {
#      -    super("create-tables", "Create all of the booking DynamoDB tables");

# (7) Confirm 'create-tables' as a real command name across BOTH repos (which modules still register it).
Get-ChildItem -Recurse -File -Path "C:\Users\arijit.kundu\projects\mercury-services","C:\Users\arijit.kundu\projects\mercury-services-commons" -Include *.java |
  ForEach-Object { $m = Select-String -Path $_.FullName -Pattern '"create-tables"'; if ($m) { "$($_.FullName): $($m.Line.Trim())" } }
#   -> only partner-integrator/pi-bl-in-processor/.../CreateTables.java (super + its test) -> not part of this migration
```
