# Runtime verification: email-sender

← [Runtime index](README.md) · [Plan](../runtime-verification.md) · [Tracker home](../README.md)

email-sender reads an email request from its queue, reads the archived failure and its error details from the workspace, renders the subject and body, sends one plain-text email through SES (at most one per 120 s per instance; the rest are dropped), and publishes a close event with the SES message id (or `messageDropped`). Migrated in PR #6.

| | QA (real) | Local test |
|---|---|---|
| Input queue | `inttra2_qa_sqs_email_outbound` | `inttra2_qa_sqs_email_outbound_dlq` (borrowed; holds test 2's two email requests) |
| Error queue | `inttra2_qa_sqs_subscription_errors` | `inttra2_qa_sqs_subscription_errors_dlq` (borrowed) |
| Workspace reads | `inttra2-qa-workspace` | the same: the archives from test 2 and one annotations object per test root |
| Sender, reply-to | `"INTTRA" <no-reply@appianway-beta.inttra.com>` | the same (verified SES identity, account in production mode) |
| Recipient | from the request: `appianway@inttra.com` | the same |
| Events | `inttra2_qa_sns_event` | the same |
| Local port | | 18083 |

Local properties (only the marked lines differ from `email-sender/conf/qa/email-sender.properties`):

```properties
email-sender.pickupSQSConfig.queueUrl=https://sqs.us-east-1.amazonaws.com/642960533737/inttra2_qa_sqs_email_outbound_dlq        # changed
email-sender.snsEventConfig.topicArn=arn:aws:sns:us-east-1:642960533737:inttra2_qa_sns_event
email-sender.sqsErrorConfig.queueUrl=https://sqs.us-east-1.amazonaws.com/642960533737/inttra2_qa_sqs_subscription_errors_dlq     # changed
email-sender.mailConfig.senderEmailAddress='"INTTRA" <no-reply@appianway-beta.inttra.com>'
email-sender.mailConfig.replyToEmailAddress=no-reply@appianway-beta.inttra.com
email-sender.environment=qa
email-sender.s3WorkspaceConfig.bucket=inttra2-qa-workspace
componentName=email-sender
server.connector.port=18083                                                                                                       # added
```

Build, configuration and start: the same steps as [error-processor](error-processor.md#how-it-is-run-locally), with `email-sender` and port 18083.

<a id="summary"></a>
## Summary in functional terms

email-sender turns a failure into the support email. **Up to the moment of sending, the new build behaves exactly like the old one:** it picks up the request, reads the stored failure and its error details, and asks SES to send from the same sender address, needing the same permission as before (so the ECS task's existing permission is enough). **Sending itself was not verified:** the role used for local runs may not send email. Arijit plans to check it on INT through the ECS task. The known defect KD-4 ([known defects](../known-defects.md#kd-4)) showed up on real AWS in both builds: a failure loops instead of being recorded.

<a id="pr-next-steps"></a>
## PR #6 Next Steps: covered?

| PR Next Step | Covered | Where |
|---|---|---|
| Boot email-sender and send an email-queue message; check the email received and the event against the v1 build | ◐ **Partly:** start, reading the request and content, and the SES call (same sender, same `ses:SendEmail` action, SESv2, no retries) ✅; the email received and the close event ⏳, because the local role may not send. To be checked on INT through the ECS task (Arijit) | [Test 3](#test-3), steps 9 and 15 |
| Stop the service while a message is being processed: clients close; the message fully processed and deleted, or delivered again | ➖ By the dispatcher check | Agreed 2026-11-19: the shutdown check runs once, on dispatcher |

<a id="test-3"></a>
## Test 3 (2026-11-19, approved by Arijit)

Plan: run v1 on v1's email request from test 2 (the new build's request hidden meanwhile), then the new build on its own; compare the two SES requests' outcome, the emails and the close events. Times are local (EST).

| # | Time | Action | Resource | Result |
|---|---|---|---|---|
| 1 | 14:44 | SES account and identities (read): `sesv2 get-account`, `sesv2 get-email-identity` | QA account | Production access, sending enabled. `appianway-beta.inttra.com` (domain) and `no-reply@appianway-beta.inttra.com` verified. (`appianway-alpha.inttra.com`, the INT sender, is not an identity in QA) |
| 2 | 14:45–14:47 | Built the jars in the build worktree | v1 `develop` `05a1d8fb`; new `07b5106f` | 46 MB / 94 MB |
| 3 | 14:47 | Local config: input and error queues changed, port 18083 added | scratchpad | |
| 4 | 14:47 | **WRITE** `s3api put-object` ×2 of the error details `{"Annotations":[{"type":"error","code":"/exception/dispatcher/business/messagePipeline/emptyFile","value":"Zero byte file"}]}`, `text/plain` | `inttra2-qa-workspace/wi01124532-rt-ep-v1/annotations`, `…-ep-v2/annotations` (the `fileName` of test 2's failure messages) | Stored, 125 bytes each |
| 5 | 14:48 | **WRITE (visibility only)** received the new build's email request with a 900 s visibility so that v1 sees only its own | `inttra2_qa_sqs_email_outbound_dlq`, message `4b69d895-…` | Hidden until about 15:03; v1's request `1264d08b-…` left visible |
| 6 | 14:48 | Started the **v1 build** | port 18083 | Started |
| 7 | 14:48 | v1 received its request, read the archive and the error details | | Reached SES |
| 8 | 14:48 | v1 `/admin/healthcheck` (read) | local | `InboundQueue -> …email_outbound_dlq` (5.5 s), `deadlocks`: healthy |
| 9 | 14:48 | **SES `SendEmail` refused:** "User '…AWSReservedSSO_INTTRA2-QATeam…' is not authorized to perform 'ses:SendEmail' on resource 'arn:aws:ses:us-east-1:642960533737:identity/no-reply@appianway-beta.inttra.com' (Status Code: 403, AccessDenied)" | SES | **No email sent.** email-sender treated it as recoverable: one retry copy sent to the borrowed queue (`failedAttempts=1`, delay 20 s) |
| 10 | 14:48 | Building the failure event failed: "Multiple entries with same key" | | **KD-4 reproduced on real AWS:** no failure event, the original not deleted ("Message is not processed; Message will reappear") |
| 11 | 14:49 | **Stopped v1 at once**, because with KD-4 every further attempt would add another retry copy | local | Port free. One attempt in total |
| 12 | 14:49 | Queue attributes (read) | `inttra2_qa_sqs_email_outbound_dlq` | About 1 visible, 1 in flight (approximate counts): v1's original, its retry copy, and the hidden new-build request. `inttra2_qa_sqs_subscription_errors_dlq` 0 |

| 13 | 15:07 | **WRITE** (agreed) received the queue (visibility 60 s), deleted v1's request, returned the new build's (visibility 0) | `inttra2_qa_sqs_email_outbound_dlq` | Deleted `1264d08b-…` (v1's original). v1's retry copy was **not** in the queue: CloudWatch shows it sent at 14:48 and one delete in the 14:47–14:52 period that the v1 log does not explain (v1 logged exactly one attempt). Recorded as unexplained; harmless. 1 message left: the new build's request |
| 14 | 15:08 | Started the **new build** on its own request (Arijit's decision: only to confirm the SES call) | port 18083 | Started. At startup cloud-sdk's email module logs 12 WARN lines "Unable to find template …json" (templates AppianWay does not use): [F24](../findings.md#f24) |
| 15 | 15:08 | New build: one send attempt | SES (SESv2) | **Refused the same way:** `SesV2Exception` "not authorized to perform 'ses:SendEmail' on resource 'arn:aws:ses:us-east-1:642960533737:identity/no-reply@appianway-beta.inttra.com' (Service: SesV2, Status Code: 403) (SDK Attempt Count: 1)". So the new build calls SESv2 `SendEmail` under **the same IAM action `ses:SendEmail` on the same identity** as v1, with no client retry (attempt count 1, as configured) |
| 16 | 15:08 | Failure handling | | As v1: recoverable, retry copy sent (20 s), then KD-4 ("Multiple entries with same key"), original not deleted |
| 17 | 15:08 | **Stopped the new build** right after its first attempt | local | Port free |
| 18 | 15:09–15:10 | **WRITE** (agreed) deleted every remaining test message | `inttra2_qa_sqs_email_outbound_dlq` | Deleted `4b69d895-…` (the new build's request) and `c08b9a11-…` (its retry copy). Queue **empty**: 0 visible, 0 in flight, 0 delayed. (The empty receives printed `None`, which the script tried to return: harmless `MissingParameter` errors, no change) |

**Result: partly verified.** What a local run with the QATeam role can show is verified: both builds start, read the request, the archive and the error details, and call SES as the same sender with the same IAM action (`ses:SendEmail`), the new build through SESv2 without client retries. **Not verified: an email actually sent and its close event**, because the role may not send. Arijit's plan: try it on INT through the ECS task (which has the permission) later.
