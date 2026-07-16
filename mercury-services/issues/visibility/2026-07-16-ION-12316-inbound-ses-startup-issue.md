# ION-12316 — visibility-inbound container startup failure (SES / AWS SDK version skew)

- **Jira:** ION-12316
- **Branch:** `feature/ION-12316-inbound-ses-issue` (single commit, not pushed)
- **Module:** `visibility/visibility-inbound`
- **Model:** Claude Opus 4.8 (1M context)

---

## 1. Summary

The `Visibility-dev` ECS container failed to start with a `NullPointerException` during Dropwizard config
processing, while every other service started normally. Root cause: `visibility-inbound` declared a **direct**
`software.amazon.awssdk:ses` dependency pinned to **2.42.28** (needed only because the module talked to Amazon SES
through the raw `SesClient` instead of the shared `cloud-sdk-api` wrapper). That direct dependency dragged the AWS
SDK **core** modules (`sdk-core`, `auth`, `regions`, `utils`, `http-client-spi`, `aws-core`) up to 2.42.28, while
`cloud-sdk-aws` (commons) supplies `profiles`/`ssm` at **2.30.24**. The mixed `profiles:2.30.24` + `sdk-core:2.42.28`
classpath makes the AWS SDK default profile-file resolution produce a **null path** (the container has no user home
directory), which throws NPE when the SSM (Parameter Store) client is built at startup — before the app/injector run.

Fix (all within `visibility-inbound`): remove the divergent direct `ses` dependency and send email through the
`sesv2` client that `cloud-sdk-aws` already provides at the commons-managed AWS SDK version (2.30.24). This unifies
the AWS SDK version, so profile-file resolution behaves exactly as in the working modules (e.g. booking). It also
overwrites the ineffective band-aid from PR #1089.

**Outcome:** one commit, `mvn -pl visibility/visibility-inbound verify` = BUILD SUCCESS (519 unit + 14 integration
tests pass). Not pushed.

---

## 2. Investigation

### 2.1 The crash (CloudWatch, read-only, profile `081020446316_INTTRA-Dev-Engg`)
```
# ECS: which service/task/log group
aws --profile 081020446316_INTTRA-Dev-Engg --region us-east-1 ecs list-services --cluster ANEINVIS-002
aws --profile 081020446316_INTTRA-Dev-Engg --region us-east-1 ecs describe-services --cluster ANEINVIS-002 --services Visibility-dev
aws --profile 081020446316_INTTRA-Dev-Engg --region us-east-1 ecs describe-task-definition --task-definition Visibility-latest-dev-Task:2
# -> container "Visibility-dev-Container", user: null, env only ENV+JVM_Xmx (no HOME), logGroup inttra-ecs-logs
aws --profile 081020446316_INTTRA-Dev-Engg --region us-east-1 logs get-log-events \
  --log-group-name inttra-ecs-logs --log-stream-name "Visibility-latest-dev/Visibility-dev-Container/<id>"
```
Log (jar `Visibility-26.07.004.jar`, container user `eoadmin`):
```
NullPointerException: Cannot invoke "java.nio.file.Path.getFileSystem()" because "<parameter1>" is null
  at software.amazon.awssdk.profiles.ProfileFile$BuilderImpl.build(ProfileFile.java:314)
  at software.amazon.awssdk.profiles.ProfileFileSupplier.lambda$defaultSupplier$2(ProfileFileSupplier.java:58)
  at software.amazon.awssdk.core.client.builder.SdkDefaultClientBuilder.mergeGlobalDefaults(...)
  at software.amazon.awssdk.services.ssm.DefaultSsmClientBuilder.buildClient(...)
  at com.inttra.mercury.cloudsdk.paramstore.factory.ParameterStoreClientFactory.createParameterStore(...:30)
  at com.inttra.mercury.config.ParameterStoreLookup.<init>(ParameterStoreLookup.java:35)
  at com.inttra.mercury.config.ConfigProcessingServerCommand.getConfigTransformer(...:27)   # commons config processing
```
So the failure is building the **SSM** client while resolving the default AWS **profile file**, whose path is null
because the container has no user home directory. This is config processing (commons), before the Guice injector or
any SES code.

### 2.2 Why only visibility (comparison with working modules)
- `Registration-26.06.004` (Jun-15 build) and `Booking-26.07.002` (Jul-14 build) start **cleanly** in the same
  container shape (image `centos:*`, `user: null`, no `HOME`, `/app/run.sh`). Booking's log even shows the SDK
  resolving `ProfileCredentialsProvider(profileName=default, profileFile=ProfileFile(sections=[]))` — an **empty**
  profile file, no NPE. Booking uses `sesv2` via `cloud-sdk-aws` at a **uniform** AWS SDK version.
- The container env is therefore **not** the differentiator by itself; the AWS SDK version consistency is.

### 2.3 Root cause — AWS SDK version skew (git + dependency tree)
`visibility-inbound/pom.xml` declared:
```xml
<dependency>
  <groupId>software.amazon.awssdk</groupId><artifactId>ses</artifactId>
  <version>${software.amazon.awssdk.ses.version}</version>   <!-- 2.42.28 -->
</dependency>
```
`mvn -pl visibility/visibility-inbound dependency:tree -Dincludes=software.amazon.awssdk` (before fix):
```
cloud-sdk-aws  ->  ssm 2.30.24, sesv2 2.30.24, s3 2.30.24, profiles 2.30.24 ...
ses:2.42.28    ->  sdk-core 2.42.28, auth 2.42.28, regions 2.42.28, utils 2.42.28,
                   http-client-spi 2.42.28, aws-core 2.42.28 ...
```
Result: `profiles:2.30.24` (from cloud-sdk-aws, declared first → wins) combined with `sdk-core/utils:2.42.28`. That
cross-version combination is what returns a null profile-file path when `user.home` is absent → NPE. `ses:2.42.28`
existed only because the code used the raw `SesClient`; `cloud-sdk` users (booking/auth/network) use `sesv2` at the
commons BOM version and never introduce the skew. The `cloud-sdk-aws` BOM is `software.amazon.awssdk:bom:2.30.24`.

### 2.4 PR #1089 (`2c467791676`) assessment
PR #1089 changed `createSesClient()` from `SesClient.create()` to a `SesClient.builder()` with an explicit
credentials-provider chain. It set only **credentials** — it did not address the profile-**file** resolution and did
not touch the version skew — so it could not fix the startup NPE (which is the SSM client, not SES). Correctly
identified by the reporter as "not correct"; this change overwrites it.

---

## 3. Root cause (stated)

`visibility-inbound` pulled AWS SDK **core** artifacts at 2.42.28 (via a direct `ses:2.42.28` dependency) mixed with
`profiles`/`ssm` at 2.30.24 (from `cloud-sdk-aws`). On a container without a user home directory, this mismatched
AWS SDK produces a null profile-file path and NPEs while building the SSM client during Dropwizard config processing.
The direct `ses` dependency existed only because email was sent through the raw `SesClient` rather than the shared
`cloud-sdk` SES (`sesv2`) client.

---

## 4. Reproduction

The failure is a build/dependency-composition + container-environment condition (null user home + AWS SDK version
skew). It is **not reproducible as a JVM unit test**, because tests run with a valid `user.home`, so even the skewed
classpath resolves a real (empty) profile file and does not NPE. It is instead evidenced/guarded by:
- `mvn dependency:tree` before vs after (Section 2.3 / 6) — the objective proof of the skew and its removal;
- the runtime CloudWatch stack trace (Section 2.1);
- unit assertions that the SES send now uses the `sesv2` client and preserves the CSV attachment (Section 5/6).

---

## 5. Fix

All changes in `visibility/visibility-inbound` (+ one property removal in `visibility/pom.xml`):

1. **`visibility-inbound/pom.xml`** — removed the direct `software.amazon.awssdk:ses` (2.42.28) dependency (and its
   netty exclusions). Added a comment warning against re-introducing any explicitly-versioned `aws-sdk` module. Email
   now uses `sesv2`, provided transitively by `cloud-sdk-aws` at the commons-managed version, so the AWS SDK stays
   unified.
2. **`visibility/pom.xml`** — removed the now-unused `software.amazon.awssdk.ses.version` property.
3. **`EmailSender.java`** — migrated from `services.ses.SesClient` (`sendRawEmail`/`SendRawEmailRequest`) to
   `services.sesv2.SesV2Client` (`sendEmail` with `EmailContent.raw(RawMessage)`), keeping the exact same MIME message
   (jakarta.mail) so the CSV error-report attachment is preserved byte-for-byte. Added a `TODO` to move to the
   `cloud-sdk-api` `EmailService` once that wrapper supports attachments (it currently drops
   `MailContent.getAttachments()` in `SesEmailServiceImpl.buildEmailContent`, so it can't yet carry the report).
4. **`VisibilityInboundApplicationInjector.java`** — replaced the PR #1089 band-aid `createSesClient()` with a
   properly-configured `SesV2Client` (explicit `Region.US_EAST_1` + `DefaultCredentialsProvider`), mirroring the
   `cloud-sdk-aws` `EmailClientFactory`.
5. Tests updated to `sesv2` (`EmailSenderTest`, `VisibilityInboundApplicationInjectorTest`), plus a new test asserting
   the raw `SendEmailRequest` carries the correct from/destination and the CSV attachment MIME.

**Backward compatibility:** the SES payload is still a raw MIME message with the same body + `INTTRA_CE_ERROR_*.csv`
attachment; only the SDK client (ses → sesv2, same underlying SES `SendRawEmail`/`SendEmail` raw content) changed.
`EmailService` is the only email-sending path in the module, and it always attaches the report — hence the pseudo
approach (direct sesv2 + TODO) rather than the attachment-less `cloud-sdk` `EmailService`.

Only `visibility-inbound` had a direct `ses` pin (verified across `visibility/*/pom.xml`); no other visibility module
required changes.

---

## 6. Tests & coverage

```
mvn -pl visibility/visibility-inbound test        # 519 unit tests, Failures: 0, Errors: 0, Skipped: 2 (pre-existing)
mvn -pl visibility/visibility-inbound verify       # + 14 integration tests (DynamoDB Local), Failures: 0, Errors: 0
mvn -pl visibility/visibility-inbound test -Dtest=EmailSenderTest,VisibilityInboundApplicationInjectorTest  # 4 tests
```
- Unit: **519** (64 classes), 0 failures. Integration (failsafe): **14**, 0 failures. BUILD SUCCESS.
- New/changed code covered: `EmailSender` (raw sesv2 send + attachment assertion + failure path), injector
  `createSesClient()` (client built), DI binding (`SesV2Client` resolvable).
- Coverage report: `visibility/visibility-inbound/target/site/jacoco/index.html`.

---

## 7. Command log (key commands, read-only unless noted)

```
git checkout -b feature/ION-12316-inbound-ses-issue develop      # branch off latest develop
git log --oneline develop..HEAD                                  # single-commit check

# root cause
git show b0f6c226ae -- .../VisibilityInboundApplicationInjector.java   # PR #1089 band-aid diff
git -C mercury-services-commons show 2d35e4d~1:commons/.../ParameterStoreLookup.java  # pre-refactor v1 SSM
mvn -pl visibility/visibility-inbound dependency:tree -Dincludes=software.amazon.awssdk  # PROVE skew 2.42.28 vs 2.30.24

# AWS (read-only) — compare containers/logs
aws --profile 081020446316_INTTRA-Dev-Engg ecs describe-task-definition --task-definition Visibility-latest-dev-Task:2
aws --profile 081020446316_INTTRA-Dev-Engg logs get-log-events --log-group-name inttra-ecs-logs --log-stream-name <visibility>
aws --profile 081020446316_INTTRA-Dev-Engg logs get-log-events --log-group-name inttra-int-lg-bkapi --log-stream-name <booking>   # booking OK, ProfileFile(sections=[])
aws --profile 081020446316_INTTRA-Dev-Engg logs get-log-events --log-group-name inttra-ecs-logs --log-stream-name <registration>  # registration OK

# verify fix
mvn -pl visibility/visibility-inbound dependency:tree -Dincludes=software.amazon.awssdk  # all core now 2.30.24
mvn -pl visibility/visibility-inbound verify
```
No AWS mutations were performed; no DynamoDB scans.

---

## 8. Build results

`mvn -pl visibility/visibility-inbound verify` → **BUILD SUCCESS**; unit 519 (2 skipped, pre-existing), integration
14; 0 failures / 0 errors.

---

## 9. References

- Jira: ION-12316
- PR being overwritten: #1089 / commit `2c467791676` (merge of `b0f6c226ae`)
- Reference modules for the cloud-sdk SES pattern: booking (`BookingEmailSenderModule`,
  `EmailClientFactory.createDefaultSesClient`), auth, network.
- Related docs: `visibility/docs/2026-06-26-aws-service-resource-details.md`,
  `visibility/docs/visibility-architecture-design-claude.md`.

---

## 10. How the other visibility modules avoided this issue (corroboration)

Read-only inspection of the sibling visibility apps in cluster
`arn:aws:ecs:us-east-1:081020446316:cluster/ANEINVIS-001` (profile `081020446316_INTTRA-Dev-Engg`):

| Service | Deployed jar | Startup result |
|---|---|---|
| `VisibilityOutbound-dev` | `VisibilityOutbound-26.07.004.jar` (Jul-14) | **Clean** — Dropwizard up, Jest + DynamoDB + SQS `MessagingClient` created via cloud-sdk-aws factory |
| `VisibilityPending-dev` | `VisibilityPending-26.07.004.jar` (Jul-14) | **Clean** — same |
| `VisibilityMatcher-dev` | `VisibilityMatcher-26.07.004.jar` (Jul-14) | **Clean** — same |
| `Visibility-ITV-GPS-Processor-dev` | `26.07.004` (Jul-14) **and** `26.07.005` (Jul-16) | **Clean** (running 1/1) — DynamoDB + SQS via cloud-sdk-aws, `DefaultCredentialsProvider`, past config processing |

```
aws --profile 081020446316_INTTRA-Dev-Engg --region us-east-1 ecs list-services --cluster ANEINVIS-001
aws --profile 081020446316_INTTRA-Dev-Engg --region us-east-1 logs get-log-events \
  --log-group-name inttra-ecs-logs --log-stream-name "<VisibilityOutbound|Pending|Matcher>-latest-dev/.../<id>" --start-from-head
```

Key observations:
- These are the same/newer build wave (26.07.004, and 26.07.005 for ITV-GPS) as `visibility-inbound`, on the **same
  commons** and the **same container shape** (image `centos:*`, `user: null`, no `HOME`, `eoadmin`, `/app/run.sh`,
  `JVM_Xmx=256m`).
- They pass **config processing** (the commons `ParameterStoreLookup` → SSM client build) and then create their AWS
  clients (`VisibilityDynamoModule`, `VisibilityMessagingModule` → SQS `MessagingClient` "using cloud-sdk-aws
  factory", `BaseDynamoDbConfig` "Resolved AWS region from DefaultAwsRegionProviderChain") **without any NPE**.
- Confirmed across `visibility/*/pom.xml`: **only `visibility-inbound` declared a direct `software.amazon.awssdk`
  artifact** (`ses`). The siblings pull every AWS client from `cloud-sdk-aws`, so their AWS SDK is uniformly the
  commons-managed 2.30.24 → the profile-file resolution returns an empty `ProfileFile` (as booking's log shows)
  instead of the null-path NPE.

**Conclusion:** the siblings didn't hit the bug precisely because they carry no divergent AWS SDK version. This is
the same mechanism as the fix — remove the skew.

---

## 11. Future-proofing commons `ParameterStoreClientFactory` for a higher AWS SDK BOM

**Why this matters now.** Today the crash is triggered by a *version skew*; with a *uniform* 2.30.24 the SSM client
builds fine even without a user home (empty `ProfileFile`). But relying on that graceful behaviour is fragile:
- A future AWS SDK BOM bump (e.g. 2.42.x, 2.4x+) can change the default `ProfileFileSupplier` / `ProfileFileLocation`
  behaviour. The `2.42.x` profile-file path resolution is exactly what produced the null `Path` at
  `ProfileFile.java:314` in the skew, so a uniform upgrade to that line could reintroduce the NPE on containers with
  no `user.home`.
- Any consumer that (legitimately or accidentally) adds another AWS module can reintroduce a skew.

The AWS clients built by commons/cloud-sdk-aws set region + credentials explicitly, so client construction should
never **hard-fail** on profile-file resolution. But we **cannot simply disable** the profile file
(`ProfileFileSupplier.empty()`), because **local development authenticates via `~/.aws/credentials`** — there is no
ECS task role locally, so the shared credentials/config file is the credential source. The correct fix is a
**null-safe profile-file supplier** that:
- **loads the real `~/.aws/config` + `~/.aws/credentials` when they can be resolved** (local dev keeps working), and
- **falls back to an empty `ProfileFile` when the location cannot be resolved** (e.g. an ECS container with no
  `user.home`/`HOME`) instead of throwing NPE.

### 11.1 Proposed change — a shared null-safe supplier + `ParameterStoreClientFactory`

New helper in cloud-sdk-aws (e.g. `com.inttra.mercury.cloudsdk.aws.config.SafeProfileFile`):

```java
public final class SafeProfileFile {
    private SafeProfileFile() {}

    /**
     * Profile-file supplier that loads ~/.aws/config + ~/.aws/credentials when the path is resolvable
     * (local dev with a real user home), and returns an empty ProfileFile when it is not (e.g. ECS containers
     * with no user.home), so building an AWS SDK v2 client never throws a NullPointerException.
     */
    public static ProfileFileSupplier supplier() {
        return SafeProfileFile::load;
    }

    private static ProfileFile load() {
        ProfileFile.Aggregator aggregator = ProfileFile.aggregator();
        addIfReadable(aggregator, ProfileFile.Type.CONFIGURATION,
                safe(ProfileFileLocation::configurationFileLocation));   // Optional<Path>, guarded
        addIfReadable(aggregator, ProfileFile.Type.CREDENTIALS,
                safe(ProfileFileLocation::credentialsFileLocation));
        return aggregator.build();   // empty when nothing could be added -> no NPE
    }

    private static Optional<Path> safe(Supplier<Optional<Path>> locator) {
        try { return locator.get(); } catch (RuntimeException e) { return Optional.empty(); }
    }

    private static void addIfReadable(ProfileFile.Aggregator agg, ProfileFile.Type type, Optional<Path> path) {
        path.filter(Files::isReadable).ifPresent(p ->
                agg.addFile(ProfileFile.builder().content(p).type(type).build()));
    }
}
```
> Confirm the exact `ProfileFileLocation` accessor names at implementation time (`configurationFileLocation()` /
> `credentialsFileLocation()` return `Optional<Path>`; the non-`Optional` `configurationFilePath()` may return null —
> whichever is used must be wrapped in `safe(...)`).

`ParameterStoreClientFactory.createParameterStore(...)` then uses it for **both** the client's default profile file
**and** the credentials provider, so local (profile) and ECS (task role) both work with no NPE:

```java
ProfileFileSupplier profiles = SafeProfileFile.supplier();

AwsCredentialsProvider credentials = (config.getCredentialsProvider() != null)
    ? config.getCredentialsProvider().getCredentialProviderDelegate()
    : DefaultCredentialsProvider.builder()
        .profileFile(profiles)          // ProfileCredentialsProvider uses the real file locally; empty on ECS
        .build();                        //   -> chain falls through to the container/task role

SsmClient ssmClient = SsmClient.builder()
    .region(config.getRegion().getRegionDelegate())
    .endpointOverride(config.getEndpointOverride())
    .credentialsProvider(credentials)
    .overrideConfiguration(b -> b
        .apiCallTimeout(config.getClientExecutionTimeout())
        .defaultProfileFileSupplier(profiles)   // never resolves a null path; still reads ~/.aws locally
        .defaultProfileName("default"))
    .build();
```

Behaviour:
- **Local dev:** `user.home` is set, `~/.aws/credentials` is readable → the real profile is loaded → profile-based
  auth and any profile settings work exactly as today.
- **ECS:** the location cannot be resolved → empty `ProfileFile` → no NPE; the `DefaultCredentialsProvider` chain
  falls through `ProfileCredentialsProvider` to `ContainerCredentialsProvider`/`InstanceProfileCredentialsProvider`
  (the task role) — matching how the sibling apps already authenticate.

Apply the same `SafeProfileFile.supplier()` override in **every** cloud-sdk-aws client factory (SSM, SES/SESv2, S3,
SQS, SNS, DynamoDB, STS, …) via the shared helper, so the whole library is uniformly resilient before any BOM bump.

### 11.2 Defense-in-depth (independent of the SDK fix)
- **Enforce version convergence.** Add a `maven-enforcer-plugin` `dependencyConvergence` (or `requireUpperBoundDeps`)
  rule and import `software.amazon.awssdk:bom` in the app parent so no module can silently pull a divergent aws-sdk
  version. This would have failed the build for `ses:2.42.28` vs the 2.30.24 BOM.
- **Container hygiene (optional).** Setting `HOME`/`-Duser.home` in the image or `run.sh` also avoids the null path,
  but it is not required once the null-safe supplier is in place, and it does not help local dev (which already has a
  home). Prefer the SDK-level fix as the primary control.

### 11.3 Test plan (commons)
- **Null-home (ECS) reproduction:** clear `user.home` (`System.clearProperty("user.home")`, restored after) and
  build the SSM client — asserts no exception with the `SafeProfileFile` supplier (and demonstrates the NPE without
  it). This reproduces the container condition inside the JVM.
- **Local (profile present):** point `SafeProfileFile` at a temp dir containing a `config`/`credentials` file (via
  the SDK's `AWS_CONFIG_FILE`/`AWS_SHARED_CREDENTIALS_FILE` env or a test override) and assert the loaded
  `ProfileFile` contains the expected profile — proves local profile-based auth is preserved.
- **Unresolvable location:** `safe(...)` swallows a throwing locator and yields an empty `ProfileFile` (no NPE).
- Existing `ParameterStoreLookupTest` remains green.

---

## 12. cloud-sdk-api / cloud-sdk-aws: add first-class attachment support (design for review)

### 12.1 Problem
`EmailService.sendEmail(from, to[, cc, bcc], MailContent)` accepts a `MailContent` that already models attachments
(`MailContent.getAttachments()` / `MailContent.Attachment{filename, content, contentType}`, implemented by
`MailContentImpl.AttachmentImpl`), **but the SESv2 impl ignores them**:
`SesEmailServiceImpl.buildEmailContent(MailContent)` only builds a `simple` `Message` (subject + html/text) and never
reads `getAttachments()`. Consequently attachment-bearing mail (e.g. visibility's CSV error report) cannot go through
the wrapper, which is why `visibility-inbound` still uses a direct `SesV2Client` (Section 5, with a TODO).

The library already contains the MIME machinery (`EmailMimeUtils`, `RawMessage`, `EmailContent.raw(...)`) — but it is
wired only into the **template** path (`sendTemplateEmail`), not the plain `sendEmail(MailContent)` path.

### 12.2 Goal
Make `EmailService.sendEmail(...)` transparently send a **raw MIME** message when `MailContent` has attachments (or
when both html+attachments require multipart/mixed), while keeping the existing **simple** path byte-for-byte
unchanged when there are no attachments (backward compatibility).

### 12.3 API (cloud-sdk-api) — no breaking changes
- `MailContent` / `MailContent.Attachment` already sufficient — **no signature changes**.
- Optional convenience (non-breaking): add a builder helper on `MailContentImpl` such as
  `addAttachment(String filename, byte[] content, String contentType)` to make call sites terse.
- Document in the `EmailService.sendEmail` javadoc that attachments in `MailContent` are now honored (raw MIME).

### 12.4 Implementation (cloud-sdk-aws)

**a) `EmailMimeUtils` — add a `MailContent`-driven overload** (the current one is `EmailRequest`+`vars` for
templates). New method builds the standard `multipart/mixed > (multipart/alternative[text,html]) + attachments`
structure:

```java
public static MimeMessage createMimeMessage(String from, List<String> to, List<String> cc, List<String> bcc,
                                            MailContent content) throws MessagingException {
    Session session = Session.getDefaultInstance(new Properties());
    MimeMessage message = new MimeMessage(session);
    message.setFrom(new InternetAddress(from));
    for (String t : to)  message.addRecipient(Message.RecipientType.TO,  new InternetAddress(t));
    if (cc  != null) for (String c : cc)  message.addRecipient(Message.RecipientType.CC,  new InternetAddress(c));
    if (bcc != null) for (String b : bcc) message.addRecipient(Message.RecipientType.BCC, new InternetAddress(b));
    message.setSubject(content.getSubject(), "UTF-8");

    MimeMultipart mixed = new MimeMultipart("mixed");
    // body wrapper (multipart/alternative: text + html)
    MimeBodyPart wrap = new MimeBodyPart();
    MimeMultipart alt = new MimeMultipart("alternative");
    if (content.getTextBody() != null) { MimeBodyPart p = new MimeBodyPart();
        p.setContent(content.getTextBody(), "text/plain; charset=UTF-8"); alt.addBodyPart(p); }
    if (content.getHtmlBody() != null) { MimeBodyPart p = new MimeBodyPart();
        p.setContent(content.getHtmlBody(), "text/html; charset=UTF-8");  alt.addBodyPart(p); }
    if (alt.getCount() == 0) { MimeBodyPart ph = new MimeBodyPart();
        ph.setContent("", "text/plain; charset=UTF-8"); alt.addBodyPart(ph); }
    wrap.setContent(alt);
    mixed.addBodyPart(wrap);

    // attachments directly under multipart/mixed (matches legacy Core layout)
    for (MailContent.Attachment a : content.getAttachments()) {
        MimeBodyPart part = new MimeBodyPart();
        String ct = (a.getContentType() != null) ? a.getContentType() : "application/octet-stream";
        part.setDataHandler(new DataHandler(new ByteArrayDataSource(a.getContent(), ct)));
        part.setFileName(a.getFilename());
        part.setDisposition(BodyPart.ATTACHMENT);
        mixed.addBodyPart(part);
    }
    message.setContent(mixed);
    message.saveChanges();
    return message;
}
```

**b) `SesEmailServiceImpl.sendEmail(from, to, cc, bcc, content)` — branch on attachments:**

```java
EmailContent emailContent = (content.getAttachments() == null || content.getAttachments().isEmpty())
    ? buildEmailContent(content)                       // existing "simple" path (unchanged)
    : buildRawEmailContent(from, to, cc, bcc, content); // new raw MIME path

SendEmailRequest request = SendEmailRequest.builder()
    .fromEmailAddress(from)
    .destination(buildDestination(to, cc, bcc))
    .content(emailContent)
    .build();
sesClient.sendEmail(request);
```
where:
```java
private EmailContent buildRawEmailContent(String from, List<String> to, List<String> cc, List<String> bcc,
                                          MailContent content) {
    try {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        EmailMimeUtils.createMimeMessage(from, to, cc, bcc, content).writeTo(out);
        return EmailContent.builder()
            .raw(RawMessage.builder().data(SdkBytes.fromByteArray(out.toByteArray())).build())
            .build();
    } catch (MessagingException | IOException e) {
        throw new SendEmailException("Failed to build raw MIME email", e);
    }
}
```

**c) Notes**
- Keep the existing exception mapping (`SdkClientException`/`SdkServiceException` → `SendEmailException`).
- `javax.mail` vs `jakarta.mail`: cloud-sdk currently uses `javax.mail` (see `EmailMimeUtils`). Keep it consistent
  within cloud-sdk-aws; the caller (visibility) is unaffected because it only passes a `MailContent`.
- For raw sends, SESv2 derives recipients from the MIME headers; still set `.destination(...)` so cc/bcc and SES
  event tracking stay consistent (as the template path already does).

### 12.5 Tests (cloud-sdk-aws)
- `sendEmail` with a single attachment → captured `SendEmailRequest` has `content().raw() != null`; raw MIME contains
  the filename, the declared content type, and `Content-Disposition: attachment`.
- `sendEmail` with **no** attachment → still uses `content().simple()` (assert `raw()` is null) — proves backward
  compatibility.
- cc/bcc propagation in both paths; multiple attachments; null/empty content-type defaults to
  `application/octet-stream`.
- Parameterized cases (AssertJ, `@Nested`) mirroring existing `SesEmailServiceImplTest` conventions.

### 12.6 Follow-up in `visibility-inbound` (after the library lands)
Once cloud-sdk-aws honors attachments, replace the direct `SesV2Client` in `EmailSender` with an injected
`EmailService` (bound via a small module like booking's `BookingEmailSenderModule`), build the report as a
`MailContentImpl` with an `AttachmentImpl` (the CSV bytes, `text/csv`), and delete the TODO. This removes the last
direct AWS SDK usage from the module and keeps it fully on cloud-sdk-api.

---

## 13. Review by Claude

Independent review of the analysis and the implemented fix. I re-read the diff (`git diff develop..HEAD`), the
changed sources, and cross-checked the referenced commons code
(`ParameterStoreClientFactory`, `EmailClientFactory`, `SesEmailServiceImpl`, `EmailMimeUtils`). I did **not** re-run
`mvn verify` — build/coverage counts in §6/§8 are taken as reported.

### 13.1 Verdict

**The root cause is correct and well-evidenced, and the fix is the right one** — minimal, at the source of the
problem, backward-compatible, and aligned with the module architecture. It correctly supersedes the PR #1089
band-aid. I would approve it for review/merge, subject to the minor observations below (none blocking).

### 13.2 What holds up under scrutiny

- **Root cause (AWS SDK version skew).** Independently confirmed the only direct `software.amazon.awssdk` artifact
  in the whole `visibility` tree is in `visibility-inbound` — after the fix even that is gone (grep over
  `visibility/**/pom.xml` returns only the new warning comment). The empirical contrast in §2.2/§10 (skewed →
  NPE at `ProfileFile.java:314`; uniform 2.30.24 siblings and booking → empty `ProfileFile(sections=[])`, no NPE)
  is strong evidence. The fix removes the skew at its source rather than masking it — correct call.
  - *Nuance (not a defect):* the precise cross-version interaction ("`profiles:2.30.24` declared first wins, mixed
    with `sdk-core:2.42.28`") is a reasonable inference rather than a line-by-line proof. It does not matter for
    correctness: the NPE originates in the SDK's **global default** profile-file supplier during
    `SdkDefaultClientBuilder.mergeGlobalDefaults`, so unifying the SDK version (the fix) is definitively correct
    independent of which artifact "won" mediation.
- **`ses` → `sesv2` is wire-equivalent.** Both send a raw MIME message to SES (`SendRawEmail` vs
  `SendEmail` with `EmailContent.raw`). The MIME bytes are produced by the unchanged `createMessageBody(...)`, so
  the payload is byte-for-byte the same. Backward-compat claim holds.
- **Envelope recipient preserved — important and easy to miss.** `createMessageBody` sets **no** `To:` header
  ([EmailSender.java:82-121](../visibility-inbound/src/main/java/com/inttra/mercury/visibility/inbound/email/EmailSender.java#L82)),
  so delivery relies entirely on the explicit envelope destination. The SES v1 path supplied it via
  `SendRawEmailRequest.destinations(to)`; the fix correctly preserves it via
  `SendEmailRequest.destination(Destination.toAddresses(to))`. Dropping that would have silently broken delivery —
  the fix gets it right.
- **Injector wiring** mirrors `EmailClientFactory.createSesV2Client` (explicit `Region.US_EAST_1` +
  `DefaultCredentialsProvider`) — consistent with the reference pattern.
- **pom guard comment** (do-not-reintroduce-a-versioned-aws-sdk) is good defensive documentation and directly
  targets the failure mode.
- **Reproduction justification is sound.** The condition (null `user.home` + classpath skew) is genuinely not
  reproducible as a plain JVM unit test; `dependency:tree` before/after is the correct objective artifact. Agreed.

### 13.3 Observations / nits (non-blocking)

1. **Attachment is nested under `multipart/alternative`, not `multipart/mixed`**
   ([EmailSender.java:108-118](../visibility-inbound/src/main/java/com/inttra/mercury/visibility/inbound/email/EmailSender.java#L108)).
   The CSV part is added to the `messageBody` (`alternative`) multipart, not to the top-level `mixed` — which is a
   MIME quirk (an "alternative" body part is semantically a rendering alternative, not an attachment; some clients
   may render it oddly). **This is pre-existing, unchanged by the fix, and must stay unchanged for byte-for-byte
   backward compatibility** — so leaving it is correct here. Worth fixing when the module moves to the library
   (§12.6): the §12.4 design places attachments directly under `multipart/mixed`, which is the correct layout.
2. **Dead statement** at [EmailSender.java:111](../visibility-inbound/src/main/java/com/inttra/mercury/visibility/inbound/email/EmailSender.java#L111):
   `csvPart.setContent("see attached report…", "text/csv")` is immediately overwritten by `setDataHandler(...)` at
   line 114. Pre-existing, harmless; clean up during the §12.6 migration.
3. **`sendEmailResult` is unused** ([EmailSender.java:55](../visibility-inbound/src/main/java/com/inttra/mercury/visibility/inbound/email/EmailSender.java#L55)).
   Pre-existing pattern (the v1 code had the same). A `log.debug(messageId)` would make it useful; optional.
4. **Region hard-coded to `US_EAST_1`** ([VisibilityInboundApplicationInjector.java:65](../visibility-inbound/src/main/java/com/inttra/mercury/visibility/inbound/config/VisibilityInboundApplicationInjector.java#L65)).
   Matches `EmailClientFactory`'s default, so acceptable; if SES ever moves region this becomes config, but that is
   out of scope.
5. **Broad `catch (Exception)`** in `sendReport` re-wraps as `ProcessingException`. Pre-existing; fine.

### 13.4 Confirmed against source

| Claim in doc | Verified |
|---|---|
| Only `visibility-inbound` had a direct `awssdk` pin | ✅ grep over `visibility/**/pom.xml` |
| `SesEmailServiceImpl.buildEmailContent` drops attachments (`.simple` only) | ✅ `SesEmailServiceImpl.java:445-465` |
| `EmailClientFactory` uses `SesV2Client` + `DefaultCredentialsProvider` + `US_EAST_1` | ✅ |
| MIME machinery exists but wired only to the template path | ✅ `EmailMimeUtils` (javax.mail) |

---

## 14. §11 ParameterStore future-proofing — review-claude

Review of the improvement proposed in **§11** (null-safe profile-file supplier in `cloud-sdk-aws`).

### 14.1 Is the mechanism right? — Yes

I confirmed [ParameterStoreClientFactory.createParameterStore](../../../mercury-services-commons/cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/paramstore/factory/ParameterStoreClientFactory.java) today
sets **no** profile-file supplier at all (lines 24-30). The NPE in the incident stack fires inside the SDK's
**global default** profile-file resolution (`ProfileFileSupplier.defaultSupplier` → `ProfileFile.build` →
`Files.newInputStream(null)`) during `mergeGlobalDefaults`, which runs on **every** client build regardless of the
credentials provider that was passed. Therefore overriding
`overrideConfiguration.defaultProfileFileSupplier(...)` with a null-safe supplier is exactly the right lever — it
pre-empts the default before it can resolve a null path. **Endorsed.**

### 14.2 Points to tighten before implementing

- **Verify the SDK API surface (the doc already flags this — do not skip it).** Against 2.30.24 confirm:
  `ProfileFile.aggregator()`, `ProfileFile.Aggregator.addFile(ProfileFile)`, `ProfileFile.Type.CONFIGURATION/CREDENTIALS`,
  and that `ProfileFileLocation.configurationFileLocation()` / `credentialsFileLocation()` return `Optional<Path>`.
  The non-`Optional` variants can return `null`, so the `safe(...)` wrapper must go around the accessor that is
  actually used. A simpler alternative worth considering: wrap the SDK's own `ProfileFileSupplier.defaultSupplier()`
  in a try/catch that falls back to `ProfileFile.aggregator().build()` (empty) — fewer moving parts, same result.
- **Null credentials-provider guard is a behaviour change.** §11.1's snippet adds
  `config.getCredentialsProvider() != null ? … : DefaultCredentialsProvider…`. The current factory calls
  `config.getCredentialsProvider().getCredentialProviderDelegate()` **unconditionally** (would NPE on null today).
  The guard is an improvement, but call it out explicitly and keep the existing behaviour for non-null configs.
- **"Apply to every factory" is the correct goal but a real surface.** SSM, SESv2, S3, SQS, SNS, DynamoDB, STS —
  and their **async** builders. Recommend routing all of them through **one** shared
  `overrideConfiguration` helper (e.g. `CloudSdkClientDefaults.apply(builder)`) so the supplier cannot be forgotten
  on a future new factory, rather than copy-pasting `.defaultProfileFileSupplier(...)` into each.
- **Local-dev preservation is the crux and the plan gets it right.** The fix must not become
  `ProfileFileSupplier.empty()` — local dev authenticates via `~/.aws`. The load-if-resolvable / empty-otherwise
  supplier keeps local profiles working while making ECS null-home safe. The §11.3 test plan
  (clear `user.home` → no NPE; temp `~/.aws` → profile loaded; throwing locator → empty) is the right matrix; add
  an assertion that with the supplier **absent** the NPE still reproduces, to prove the test guards the regression.

### 14.3 Strongly endorse §11.2 (build-time convergence guard)

The `maven-enforcer-plugin` `dependencyConvergence` / `requireUpperBoundDeps` + imported `software.amazon.awssdk:bom`
is the **cheapest, highest-value** control and would have failed the build for `ses:2.42.28` vs the 2.30.24 BOM —
catching this class of bug before it ever reached a container. I confirmed there is currently **no** enforcer
convergence rule in `visibility/pom.xml` or the repo root. Recommend adding it regardless of the SDK-level fix; the
two are complementary (enforcer stops the skew; `SafeProfileFile` stops the hard-fail if a skew or BOM bump ever
slips through).

### 14.4 Scoping recommendation

This is a **commons/cloud-sdk-aws** change, not part of `visibility`'s ION-12316 fix (which is already complete and
sufficient for the incident). Track §11 as its own commons ticket with its own tests and rollout, so it doesn't
enlarge or delay the single-commit visibility fix. Priority: do it before the next AWS SDK BOM bump — a uniform
upgrade to the 2.42.x line is exactly what produced the null `Path`, so it could reintroduce the NPE fleet-wide on
home-less containers even without a skew.

---

## 15. §12 SES attachment capability gap — review-claude

Review of the improvement proposed in **§12** (first-class attachment support in `cloud-sdk-api`/`cloud-sdk-aws`).

### 15.1 Gap confirmed and correctly diagnosed

Verified: [SesEmailServiceImpl.buildEmailContent](../../../mercury-services-commons/cloud-sdk-aws/src/main/java/com/inttra/mercury/cloudsdk/email/impl/SesEmailServiceImpl.java) (lines 445-465)
builds only `EmailContent.builder().simple(message)` and **never reads `content.getAttachments()`** — so the wrapper
silently drops attachments on the `sendEmail(MailContent)` path. This is precisely why `visibility-inbound` still
uses a direct `SesV2Client` with the documented TODO. The claim that the MIME machinery already exists but is wired
**only** to the template path is also correct: `EmailMimeUtils` (javax.mail) has `createMimeMessage(EmailRequest,
vars)` and raw builders, but nothing driven from `MailContent`. **Diagnosis accurate.**

### 15.2 Design assessment — sound and backward-compatible

- **Branch-on-attachments** (`simple` when none, `raw` MIME when present) keeps the no-attachment path byte-for-byte
  unchanged — the correct backward-compat strategy. Endorsed.
- **No API break:** `MailContent`/`Attachment` already model attachments, so no signature changes. Correct.
- **Correctness upgrade:** §12.4 places attachments directly under `multipart/mixed`. That is **more correct** than
  both visibility's current code and `EmailMimeUtils`'s second builder, which nest the attachment under
  `multipart/alternative` — a quirk the library's **own javadoc flags** (`EmailMimeUtils` lines ~199-207 / ~247-263:
  "Notice the Attachment is nested under the multipart/alternative part instead of being directly under the
  multipart/mixed part"). Recommend the mixed-level layout as designed.

### 15.3 Points to tighten before implementing

- **Reuse, don't fork, the MIME builder.** `EmailMimeUtils` already contains three MIME-construction methods. Adding
  a fourth parallel `createMimeMessage(from,to,cc,bcc,MailContent)` risks a **fourth** divergent layout. Prefer
  refactoring the shared "mixed → (alternative[text,html]) + attachments" assembly into one private helper that both
  the template path and the new `MailContent` path call.
- **javax vs jakarta — the design's note is right; keep it internal.** Confirmed `EmailMimeUtils` uses
  `javax.mail`, while the visibility caller uses `jakarta.mail`. Because visibility would only pass a `MailContent`
  (POJO) into the library, the caller is unaffected — so **do not block attachment support on a jakarta migration**.
  But flag separately: cloud-sdk-aws email on legacy `javax.mail` is tech debt worth its own migration ticket
  (mercury is on jakarta elsewhere).
- **Raw sends still need `.destination(...)`.** §12.4(c) is right to keep it (SESv2 derives recipients from MIME
  headers for raw, but explicit destination keeps cc/bcc + SES event tracking consistent). This is the same subtlety
  that mattered in the visibility fix (§13.2) — good that the design carries it through.
- **Exception mapping:** keep the existing `SdkClientException/SdkServiceException → SendEmailException` behaviour;
  wrap `MessagingException/IOException` from MIME building into the same `SendEmailException` (as §12.4(b) shows).

### 15.4 Tests

§12.5's matrix is right (attachment → `content().raw() != null` and MIME contains filename/content-type/disposition;
no attachment → `content().simple()` with `raw()` null; cc/bcc; multiple attachments; null content-type default).
**Add** an explicit round-trip/byte-comparison assertion for the no-attachment `simple` path against the pre-change
output, to lock in backward compatibility.

### 15.5 Migration follow-up (§12.6)

Sound. Once the library honors attachments, `visibility-inbound` should inject `EmailService`, build a
`MailContentImpl` + `AttachmentImpl` (CSV bytes, `text/csv`), drop the direct `SesV2Client`, and delete both the
TODO and the local MIME assembly — removing the last direct AWS SDK usage from the module. That also naturally fixes
the §13.3(1) `alternative`-vs-`mixed` quirk. Sequence it as: land §12 in commons → then this follow-up in a
separate `visibility` ticket.

### 15.6 Priority relative to §11

§11 fixes a **startup-crash** class of bug (fleet-wide, triggered by any future BOM bump) — higher priority. §12 is
a **capability gap / tech-debt** cleanup that removes visibility's last divergent AWS usage — valuable but not
urgent, since the current direct-`SesV2Client` approach works and is at the unified SDK version.
