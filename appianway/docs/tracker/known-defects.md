# Known existing defects

← [Tracker home](README.md)

Defects found in today's code while each service was migrated. None of them is caused by the AWS SDK upgrade, and the upgrade fixes none of them: it changes no behaviour ([A12](actions.md#a12); review summary decision 4). Each one has a **disabled test** in the service that asserts the correct behaviour, fails when enabled, and was checked to pass with the fix given here. **They are not fixed in this program** ([D43](decisions.md#d43), 2026-11-20: no one has reported any of them).

Services not migrated yet: their defects, found during the design review, are listed in the [review summary §4](../redesign/2026-10-30-apway-WI01124532-review-summary.md) (distributor, distributor-rest, ingestor, watermill). They move to this page with a test when their PR is done.

## Summary

| # | Service | Defect | Since | Severity | Disabled test | Finding |
|---|---|---|---|---|---|---|
| [KD-1](#kd-1) | dispatcher | A failed send to the next queue routes the file twice, and its failure event is lost (same shared-handler defect expected in distributor and distributor-rest: [see](#kd-1-other-services)) | June 2018 | Medium-high | `DispatcherKnownDefectsTest.aFailedRoutedSendIsRetriedOnceAndItsFailureEventPublished` | [F18](findings.md#f18) |
| [KD-2](#kd-2) | dispatcher | The error-rate health check never turns unhealthy | May 2018 | Low | `DispatcherKnownDefectsTest.theErrorRateHealthCheckCountsFailedMessages` | [F19](findings.md#f19) |
| [KD-3](#kd-3) | dispatcher | A temporary storage failure while expanding a zip is not retried | Nov 2018 | Medium | `DispatcherKnownDefectsTest.aStorageFailureWhileExpandingAZipIsRetried` | [F20](findings.md#f20) |
| [KD-4](#kd-4) | email-sender | Every failure loops until the queue's redrive, and its failure event is lost | before 2017 (hidden: the test had no `@Test` since 2017) | Medium | `EmailSenderKnownDefectsTest.aFailureIsHandledOnceWithItsFailureEventAndTheMessageDeleted` | [F16](findings.md#f16) |
| [KD-5](#kd-5) | event-writer | A failed event write is swallowed: the message is deleted and the event lost | July 2017 | Medium | `EventWriterKnownDefectsTest.aFailedWriteLeavesTheMessageOnTheQueue` | review summary §4 |
| [KD-6](#kd-6) | event-writer | The error-rate health check never counts a failed write | July 2017 | Low | `EventWriterKnownDefectsTest.aFailedWriteMarksTheMeterTheErrorRateHealthCheckReads` | review summary §4 |
| [KD-7](#kd-7) | error-processor | With several recipients, every email goes to the first recipient | Sept 2017 | Medium | `ErrorProcessorKnownDefectsTest.eachEmailQueueMessageCarriesItsOwnRecipient` | review summary §4 |
| [KD-8](#kd-8) | splitter | Groups of one batch routed in parallel share the parent's projections: a split document can carry another document's control number | June 2018 | Medium-high | `SplitterKnownDefectsTest.eachSplitDocumentKeepsItsOwnControlNumberWhenGroupsAreRoutedInParallel` | review summary §4 |
| [KD-9](#kd-9) | splitter | The whole partner document is logged at INFO | Sept 2023 | Medium (data in logs) | `SplitterKnownDefectsTest.theDocumentContentIsNotLogged` | review summary §4 |
| [KD-10](#kd-10) | splitter | A document that needs no splitting and fails its authorization check is retried (or sent to the error queue) **and** routed | Nov 2018 | Medium | `SplitterKnownDefectsTest.aDocumentWhoseAuthorizationCheckFailsIsNotAlsoRouted` | splitter pre-review |
| [KD-11](#kd-11) | splitter | The error-rate health check never turns unhealthy (as KD-2) | April 2017 | Low | `SplitterKnownDefectsFuncTest.theErrorRateHealthCheckCountsFailedMessages` | splitter pre-review |
| [KD-12](#kd-12) | transformer | The control-number conflict-retry counter resets only on success: after one reservation gives up, later ones fail at their first conflict | March 2019 | Medium (under contention) | `TransformerKnownDefectsTest.eachBlockReservationGetsItsOwnTenConflictRetries` | review summary §4 |
| [KD-13](#kd-13) | transformer | A permanent failure builds the parameters twice: the document is read again, an outbound document gets a second supplement and a second control number | May 2018 | Low-medium | `TransformerKnownDefectsFuncTest.aPermanentFailureWritesOneSupplementAndReservesOneControlNumber` | review summary §4 |
| [KD-14](#kd-14) | transformer | When those parameters cannot be built again, the error handler throws a NullPointerException and the message loops until the redrive | May 2018 | Medium | `TransformerKnownDefectsTest.anUnknownRoutingFallsBackToTheConfiguredErrorQueue` | review summary §4 |
| [KD-15](#kd-15) | ingestor | One unreadable message (a `HEALTHCHECK` published to the event topic) drops the events of every other message of its batch: all deleted, never indexed | July 2018 | Medium (lost tracking) | `IngestorKnownDefectsTest.oneUnreadableMessageDoesNotDropTheOtherEventsOfTheBatch` | review summary §4 |
| [KD-16](#kd-16) | ingestor | Event documents are indexed without an id: a batch delivered again adds a second copy of each event document | July 2018 | Low-medium (duplicate rows in tracking) | `IngestorKnownDefectsTest.anEventDeliveredAgainReplacesItsDocumentInsteadOfAddingASecondOne` | review summary §4 |
| [KD-17](#kd-17) | ingestor | When Elasticsearch cannot be reached (3 tries), the batch is deleted anyway: its events are never indexed | July 2018 | Medium (lost tracking during an outage) | `IngestorKnownDefectsTest.whenElasticsearchCannotBeReachedTheBatchStaysOnTheQueue` | ingestor pre-review |
| [KD-18](#kd-18) | distributor | Every failure loops: the shared error handler fails on the duplicate `pickupQueue` token, no failure event, the message comes back until the redrive (as KD-4) | March 2021 | Medium | `DistributorKnownDefectsFuncTest.aFailureIsHandledOnceWithItsFailureEventAndTheMessageDeleted` | duplicate-token check 2026-11-19 |
| [KD-19](#kd-19) | distributor | The error-rate health check never turns unhealthy (as KD-11) | June 2017 | Low | `DistributorKnownDefectsFuncTest.theErrorRateHealthCheckCountsFailedMessages` | distributor golden test |
| [KD-20](#kd-20) | distributor | Not idempotent on redelivery: a message delivered again delivers a second file under a new random name (and leaves an orphan zip) | June 2017 | Low-medium | none (no small fix: the random part of the name is by design) | review summary §4 |
| [KD-21](#kd-21) | distributor | A pickup message that is not valid `MetaData` JSON is parsed outside the error handling: no event, not deleted, back until the redrive | June 2017 | Low | none (what to do with an unreadable message is a decision, not a small fix) | distributor pre-review |
| [KD-22](#kd-22) | distributor-rest | **Security:** one cached OAuth token for every subscription: a subscriber's token is sent to other subscribers' endpoints until a 401 | March 2021 | High (credentials to the wrong party) | `DistributorRestKnownDefectsFuncTest.eachSubscriberGetsItsOwnToken` | review summary §4 ([A5](closed-items.md#a5): not raised with QA, Arijit) |
| [KD-23](#kd-23) | distributor-rest | A FAILURE answer is wrapped as recoverable: retried until the redrive, no error-queue message | March 2021 | Medium | `DistributorRestKnownDefectsFuncTest.aFailureAnswerIsHandledAsANonRecoverableFailure` | distributor-rest golden test |
| [KD-24](#kd-24) | distributor-rest | A handled failure fails on the duplicate `pickupQueue` token (as KD-18): no event, not deleted | March 2021 | Medium | `DistributorRestKnownDefectsFuncTest.aHandledFailureIsDeletedWithItsFailureEvent` | duplicate-token check 2026-11-19 |
| [KD-25](#kd-25) | distributor-rest | A webhook that is not the subscription's first action is built from the first action's parameters: nothing posted, loops | March 2021 | Medium | `DistributorRestKnownDefectsFuncTest.aWebhookThatIsNotTheFirstActionIsPostedToItsOwnEndpoint` | distributor-rest golden test |
| [KD-26](#kd-26) | distributor-rest | A pickup message that is not valid `MetaData` (or has no projections) is parsed outside the error handling: no event, not deleted, back until the redrive (as KD-21) | March 2021 | Low | none (as KD-21) | distributor-rest pre-review |
| [KD-27](#kd-27) | watermill-publisher (with pi-statusevents-out-processor) | Non-ASCII characters are published to Watermill garbled (`Tôkyô` as `TÃ´kyÃ´`): the producer writes UTF-8 bytes under an ISO-8859-1 declaration, the publisher decodes ISO-8859-1 | at least Oct 2026 (seen in QA) | Medium (wrong data at e2open) | none: the fix belongs to the producer (recorded by the golden test, [fixtures](runtime/fixtures/qa-se-watermill/README.md)) | watermill-publisher golden test |
| [KD-28](#kd-28) | watermill-publisher | One failed dead-letter redrive run ends the redrive until the next restart | May 2021 | Medium | `WatermillPublisherKnownDefectsTest.aFailedRedriveRunDoesNotEndTheRedrive` | design (Risks) |
| [KD-29](#kd-29) | watermill-publisher | Every reconnect to Watermill leaves one more cleaner thread running | May 2021 | Low (thread leak) | `WatermillPublisherKnownDefectsTest.aReconnectDoesNotLeaveAnotherCleanerThreadRunning` | design (Risks) |
| [KD-30](#kd-30) | watermill-publisher | A failed delete on an ack cancels the stream and drops every other pending ack: those events are published twice | May 2021 | Medium (duplicates at e2open) | `WatermillPublisherKnownDefectsTest.aFailedDeleteOnAnAckDoesNotDropTheOtherAcks` | design (Risks) |
| [KD-31](#kd-31) | watermill-publisher | A message that never succeeds cycles between the DLQ and the pickup queue for ever (the redrive keeps no count) | May 2021 | Low | none: fix not decided | design (Risks) |
| [KD-32](#kd-32) | watermill-publisher | The stream-reset flag is not `volatile`: a listener may miss a reset and keep sending on a closed stream | May 2021 | Low | none (memory visibility, not reproducible in a test) | design (Risks), pre-review |
| [KD-33](#kd-33) | watermill-publisher | A failure while building the Guice injector is printed and swallowed; startup then fails with a `NullPointerException` instead of the real cause | May 2021 | Low | none (fix: let the exception propagate) | watermill-publisher pre-review |

Not defects, recorded as findings only: [F23](findings.md#f23) zip entries inside folders cannot be routed (dispatcher, since 2018, nobody has reported it); [F12](findings.md#f12) event-writer drops a message whose event has a field it does not know (candidate).

## For QA: what you would see and how to observe it

| # | Defect | When it happens | What you would see | How to observe in QA |
|---|---|---|---|---|
| KD-1 | dispatcher: a failed send to the next queue routes the file twice | Sending the `MetaData` to splitter or the booking bridge fails (SQS outage, throttling, permissions) | Dispatcher log: "Multiple entries with same key", then "Message is not processed; Message will reappear". Later the same file reaches splitter twice; the failure event of the first attempt is missing from the event store | Temporarily deny `sqs:SendMessage` on the splitter queue to the dispatcher role, drop a file, then restore the permission. Expected (bug): two `MetaData` messages in the splitter queue for one file |
| KD-2 | dispatcher: error-rate health check never turns unhealthy | Any failures | `/healthcheck` stays healthy however many files fail | Drop several zero-byte files. Admin `/metrics`: `ErrorHandler.messages-failed` goes up, `DispatcherTask.messages-failed` stays 0, `errorsPerSecondAverage` stays healthy |
| KD-3 | dispatcher: temporary S3 failure while expanding a zip is not retried | S3 timeout or throttling while reading the zip or writing its entries | The zip lands in the error queue as a permanent error; entries written before the failure are processed, the rest are lost | Hard to trigger on purpose: briefly remove the dispatcher role's write access to the inbound bucket while dropping a zip. Expected (bug): an error-queue message, no retry on the pickup queue |
| KD-4 | email-sender: failures loop, failure event lost | Any failure (workspace object missing, template error, SES failure) | email-sender log: "Multiple entries with same key". The message is handled (sent back or to the error queue) again and again until the queue's redrive; no failure event in the event store | Send an email-queue message whose workspace files do not exist. Expected (bug): repeated "Multiple entries" warnings for the same message, retries or error-queue messages for each delivery |
| KD-5 | event-writer: failed write loses the event | The event-store write fails (S3 outage, permissions) | The message is deleted; the event is missing from the event store; nothing in the dead-letter queue | Temporarily deny `s3:PutObject` on the event-store bucket to the event-writer role, publish one event. Expected (bug): queue empty, DLQ empty, event not stored |
| KD-6 | event-writer: error-rate check never counts failures | Failed writes | `/healthcheck` stays healthy while writes fail | During the KD-5 check: `errorsPerSecondAverage` stays healthy, its meter in `/metrics` stays 0 |
| KD-7 | error-processor: every email goes to the first recipient | `errorEmailRecipient` lists two or more addresses | All error emails go to the first address; the others receive nothing | Configure two recipients, cause one failure in any service. Expected (bug): every email-queue message carries the first address |
| KD-8 | splitter: a split document carries another document's control number | A batch whose documents fall into several groups (for example several interchanges or groups in one file) | A downstream document (booking, SI, event) with the `documentControlNumber` of another document of the same file; occasionally the whole batch fails and is retried (`ConcurrentModificationException`) | Drop one EDIFACT file with several UNG groups or interchanges. Compare each split `MetaData` in the next queue with its own content. Expected (bug): some control numbers do not match their document |
| KD-9 | splitter: partner documents in the log | Every file | splitter log at INFO: "String content of file … is …" followed by the whole document | Drop any file; search the splitter log group for its content. Expected (bug): the full document is there |
| KD-10 | splitter: a document is both retried and routed | A document that is not split (XML booking, desktop and other single-document formats) while its authorization check fails, typically Network Services unavailable | The document reaches the next service, and again 300 s later (the retry), with a failure event for the first attempt | Hard to trigger on purpose: make Network Services unreachable for splitter while dropping an XML booking. Expected (bug): one `MetaData` in the next queue at once and a second one after 300 s |
| KD-11 | splitter: error-rate health check never turns unhealthy | Any failures | `/healthcheck` stays healthy however many files fail | Drop several unparseable files. Admin `/metrics`: `ErrorHandler.messages-failed` goes up, `SplitterTask.messages-failed` stays 0 |
| KD-12 | transformer: control-number retries do not reset | Heavy contention between transformer instances reserving blocks at the same time | After one "Failed to generate sequence Id after 10 re-tries!", later documents of that instance fail at their first conflict until it restarts | Hard to trigger on purpose; look for that message in the transformer logs followed by further failures without "Retrying" lines |
| KD-13 | transformer: second supplement and control number | Any permanent failure of an outbound document (map missing, structural error) | Two supplement objects in the workspace for one document; a control number skipped | Send an outbound document whose integration profile format names a map that does not exist; count the supplement objects under its root workflow |
| KD-14 | transformer: NullPointerException loop | A permanent failure whose parameters cannot be built again (integration profile format missing) | transformer log: NullPointerException in `TransformerErrorHandler.getErrorQueue`; the message is delivered again until the redrive | Send a `MetaData` naming a non-existent integration profile format id; watch the receive count grow |
| KD-15 | ingestor: events lost after an unreadable message | A received batch (up to 10 messages) that also holds something that is not a list of events, for example a `HEALTHCHECK` published to the event topic | Workflows missing steps in transaction tracking (the `txtrack-event-*` index); ingestor log: "Exception in Ingestor" with a JSON parse error | Publish a plain-text message to the event topic while files flow; compare the events in the event store with the documents indexed for the same minute |
| KD-16 | ingestor: duplicate event documents | A batch delivered again: its delete failed, or it took longer than the queue's visibility timeout | The same event twice in transaction tracking (two documents with one `eventId` in `txtrack-event-*`) | Search a day's event index for an `eventId` with more than one document |
| KD-17 | ingestor: events lost while Elasticsearch is down | Elasticsearch unreachable or failing for more than about a second | Gaps in transaction tracking for the outage; ingestor log: "Elastic Service call failed. Attempt:" then "Exception in Ingestor" with a RecoverableException, and the messages deleted | Compare the event store with the tracking index for the minutes of an Elasticsearch incident |
| KD-18 | distributor: failures loop | Any failure: missing integration profile format, missing delivery attribute, Network Services down | No failure event for the file; the message is received again and again (`ApproximateReceiveCount` grows) until it reaches the file-delivery DLQ; an error-queue message and an annotations object per attempt | Send a file-delivery `MetaData` without `outboundIntegrationProfileFormatId`; watch the error queue get one message per receive |
| KD-19 | distributor: error-rate health check never unhealthy | Any failures | `/healthcheck` stays healthy however many deliveries fail | As KD-18; admin `/metrics`: `ErrorHandler.messages-failed` goes up, `DistributorTask.messages-failed` stays 0 |
| KD-20 | distributor: a second delivery on redelivery | A message received again after a partial run (crash between the two copies, or a visibility timeout) | Two files for one document in the partner's outbound folder, with different random suffixes | Hard to trigger; look for two delivered files of one workflow id in the outbound bucket |
| KD-22 | distributor-rest: one token for all subscribers | Two subscriptions with different OAuth endpoints delivered by one running instance | The second subscriber's endpoint receives a bearer token its own OAuth endpoint never issued (and usually answers 401, which triggers a new token for it) | Deliver to two webhook subscriptions in turn; the second subscriber's access log shows the first one's token |
| KD-23 | distributor-rest: rejected documents retried | The subscriber answers with a non-SUCCESS status | The same document posted again on every receive until the DLQ; no error-queue message | Point a subscription at an endpoint answering a FAILURE code |
| KD-24 | distributor-rest: handled failures loop | A failure the task handles (I/O error reading the document; a FAILURE answer once KD-23 is fixed) | No failure event; the message comes back until the redrive | As KD-18 |
| KD-25 | distributor-rest: webhook not first | A subscription with another action (for example an email) before its EDI webhook | Nothing is delivered; the message loops until the DLQ | Configure such a subscription in Network Services and deliver to it |
| KD-27 | watermill-publisher: garbled characters | Any status event with a non-ASCII character (location names such as `Tôkyô`) | The event published to Watermill has `TÃ´kyÃ´`; the original XML in `transactionAsXml` too | QA log `AppianWay-watermill-publisher-latest-qa`, the `Message :` line: `\u00c3\u00b4` where the document has `ô` |
| KD-28 | watermill-publisher: redrive stops | One SQS error during a redrive run (throttling, a network error) | Messages pile up in `inttra2_qa_sqs_watermill_ce_dlq` and are never moved back, until the service restarts; no "Executing DeadLetterService..." line every 30 min any more | Watch the DLQ's `ApproximateNumberOfMessages` and the 30-minute log line |
| KD-29 | watermill-publisher: thread leak | Repeated Watermill disconnects | Thread count of the task grows by one per reconnect ("Creating new streams...." lines) | Container metrics, or a thread dump |
| KD-30 | watermill-publisher: duplicates after a failed delete | A delete on ack fails (SQS error) | The other events sent on that stream are published to Watermill a second time after the 60 s visibility timeout | Hard to trigger; duplicate message ids at e2open |
| KD-31 | watermill-publisher: poison message cycles | A document that is acked never, or always fails to publish | The same message goes pickup → DLQ (after 5 receives) → pickup every 30 min, for ever | Watch one message id in the logs over several hours |

## Details

<a id="kd-1"></a>
### KD-1 · dispatcher: a failed send to the next queue routes the file twice (since June 2018)

**Technical.** When the `MetaData` cannot be sent to the next queue, the error handler builds the failure event from the task's tokens plus its own, and both hold `pickupQueue` and `dropOffQueue`. `ImmutableMap` rejects the duplicate keys, so building the event fails and the message is not deleted.

**Functional effect.** The retry copy and the re-delivered original are both processed, so the file reaches the next service (splitter or booking bridge) twice, and the failed attempt has no lineage event. It happens only when that send fails (SQS outage, throttling, permissions). During a longer outage, each failing attempt spawns another retry copy without deleting itself, so copies pile up until SQS's redrive limit moves them to the dead-letter queue.

**Who is involved.** The error handler is the shared `ErrorHandler` (`shared/.../task/ErrorHandler.java`); dispatcher uses it through `DispatcherErrorHandler`, which only adds dispatcher's error codes, so it runs inside dispatcher. The event that is lost is **dispatcher's** failure close-run event (published to the SNS event topic). event-writer is not at fault: it stores what arrives on that topic, and this event never arrives.

**The SQS rule behind it.** Receiving a message does not remove it. SQS only hides it for the queue's visibility timeout. The service must delete it when done. If no delete comes, SQS delivers the message again.

**Code path.**

1. The task records both queues, then the send fails ([DispatcherTask.java:200-206](../../dispatcher/src/main/java/com/inttra/mercury/dispatcher/task/DispatcherTask.java)):
   ```java
   map.put(Event.Token.PICK_UP_QUEUE, configuration.getSqsPickupConfig().getQueueUrl());   // tokens now hold pickupQueue
   map.put(Event.Token.DROP_OFF_QUEUE, outputQueueUrl);                                     // ... and dropOffQueue
   queueClient.sendMessage(outputQueueUrl, metaData.toJsonString());                        // throws
   ```
   The task's `catch` (line 142) calls `errorHandler.handleException(message, ..., tokens, ex)` with that same map.
2. The handler sends the **retry copy**, which works ([ErrorHandler.java:143-151](../../shared/src/main/java/com/inttra/mercury/shared/task/ErrorHandler.java), [ErrorHelper.java:201-205](../../shared/src/main/java/com/inttra/mercury/shared/task/errorhandler/ErrorHelper.java)):
   ```java
   closeRunTokens = message.sendBackToPickupQueue(pickupQueue);            // a NEW message: same body, failedAttempts + 1, delay 20 s
   closeRunTokens.put(PICK_UP_QUEUE, pickupQueue);                         // the handler's own pickupQueue (dropOffQueue is already in it)
   publishCloseRunEvent(..., closeRunTokens, tokens, exception);
   ```
   This is dispatcher's retry design: put a fresh copy back with a delay, and get rid of the original.
3. Building the failure event throws ([ErrorHandler.java:172-173](../../shared/src/main/java/com/inttra/mercury/shared/task/ErrorHandler.java)):
   ```java
   eventLogger.logCloseRunEvent(..., ImmutableMap.<String, String>builder().putAll(tokens).putAll(closeRunTokens).build());
   // IllegalArgumentException: Multiple entries with same key
   ```
   No failure event is published, and the exception leaves `process(..)`.
4. The original is not deleted ([AbstractTask.java:62-70](../../shared/src/main/java/com/inttra/mercury/shared/task/AbstractTask.java)):
   ```java
   processing.run();                                   // process(..) throws
   sqs.deleteMessage(this.queueUrl, receiptHandle);    // never reached
   } catch (Exception ex) {
       log.warn("Message is not processed; Message will reappear ", ex);
   }
   ```

**Result: two live messages for one file** (normally only the retry copy remains):

| Time | Message | What happens |
|---|---|---|
| 0 s | original | received; send fails; retry copy sent; event fails; **not deleted** |
| +20 s | retry copy (`failedAttempts=1`) | delivered after its delay |
| + visibility timeout | original (`failedAttempts` unchanged) | delivered again, because it was never deleted |

Once SQS works again, both succeed: two workspace copies, two `MetaData` messages to splitter, two downstream transactions for one inbound file.

**Fix (checked, not committed).** Remove the two keys from the task's tokens before calling the handler (`tokens.remove(Event.Token.PICK_UP_QUEUE); tokens.remove(Event.Token.DROP_OFF_QUEUE);`). Alternative in `shared`: let the handler's own values win (`buildKeepingLast()`), which fixes every affected service at once (see below).

<a id="kd-1-other-services"></a>
**The same defect in other services (checked 2026-11-19).** The merge is in the shared `ErrorHandler`, which always adds `pickupQueue` and `dropOffQueue` itself. A service is affected when the tokens it passes to `handleException` already hold either key:

| Service | Tokens passed to the shared handler | Affected? | When |
|---|---|---|---|
| dispatcher | the task's map, which gets `pickupQueue` + `dropOffQueue` just before the routed send | **Yes** (KD-1) | Only when the routed or booking-bridge send fails |
| email-sender | `ImmutableMap.of(PICK_UP_QUEUE, …)` | **Yes** (KD-4) | Every failure |
| distributor | `ImmutableMap.of(PICK_UP_QUEUE, pickupQueueUrl)` (`DistributorTask.java:71`); `DistributorErrorHandler` only adds error codes | **Yes, expected** | Every failure |
| distributor-rest | `ImmutableMap.of(PICK_UP_QUEUE, …)` (`DistributorTask.java:91`) to the shared handler | **Yes, expected** | Every handled failure (`NonRecoverableException`, `IOException`) |
| error-processor | `new HashMap()` (empty) | No | |
| transformer | only the supplement token | No | |
| splitter | empty map to the shared handler; its own `SplitErrorHandler` merges through a `HashMap` | No | |
| ingestor, event-writer | own error handling, not the shared merge | No | |
| router (not in the reactor build, retired) | `PICK_UP_QUEUE` | Would be | Out of scope |

"Expected" = the same code pattern as email-sender, where a test confirmed it. distributor and distributor-rest get their own disabled test in their migration PRs ([A12](actions.md#a12)). For these two the effect is the email-sender one: **every** failure is handled, but its failure event is lost and the message comes back until the queue's redrive. One fix in `shared` would close all four.

<a id="kd-2"></a>
### KD-2 · dispatcher: the error-rate health check never turns unhealthy (since May 2018)

**Technical.** The check watches `DispatcherTask.messages-failed`, but failures are counted in `ErrorHandler.messages-failed`. `DispatcherApplication` gives the check `name(DispatcherTask.class, MESSAGES_FAILED_METRIC)`; the counting is `@Metered(name = MESSAGES_FAILED_METRIC)` on the shared `ErrorHandler.handleException`, and metrics-guice names that meter after the class that declares the method.

**Functional effect.** `errorsPerSecondAverage` (unhealthy at an average of 5 or more failures a second over 5 minutes) stays healthy however many files fail, so anything that relies on it (load balancer, monitoring) does not notice. File processing is not affected. Probably every service whose error handler extends the shared one has the same mismatch.

**Fix (checked).** Give the check the meter the handler marks, `name(ErrorHandler.class, MESSAGES_FAILED_METRIC)`, or mark the task's meter. The disabled test reads the meter the registered check holds, so it passes with either.

<a id="kd-3"></a>
### KD-3 · dispatcher: a temporary storage failure while expanding a zip is not retried (since November 2018)

**Technical.** `ZipPreprocessor.process` catches every exception and re-throws it as `new RuntimeException("Exception in zip processor", e)`. The error handler retries only a `RecoverableException`, so the recoverable storage failure inside is treated as permanent.

**Functional effect.** A temporary S3 problem while reading a zip or writing its entries sends the zip to the error queue as a permanent failure instead of retrying it (error details written, failure `MetaData` to the error queue, message deleted). Entries written before the failure are processed; the rest are lost. The dispatcher design page says such a zip "is re-expanded on retry"; that is not today's behaviour.

**Fix (checked).** Re-throw a `RecoverableException` unchanged before the generic `catch`.

<a id="kd-4"></a>
### KD-4 · email-sender: every failure loops until the queue's redrive (existing before 2017)

**Technical.** Same family as KD-1: the task passes a `pickupQueue` token to the error handler, which adds `pickupQueue` again when it builds the failure event, so `ImmutableMap` throws "Multiple entries with same key".

**Functional effect.** Every failure is handled (sent back to the pickup queue with a delay, or to the error queue), but its failure event is never published and the message is not deleted, so it comes back and is handled again until the queue's redrive policy moves it away. It was hidden because the v1 error-flow functional test had no `@Test` since 2017.

**Fix (checked).** The task passes no `pickupQueue` token (one line), or the shared fix of KD-1.

<a id="kd-5"></a>
### KD-5 · event-writer: a failed event write is swallowed (since July 2017)

**Technical.** `S3StoringMessageHandler` catches the failure of the event-store write and only logs it, so `AbstractTask` deletes the message.

**Functional effect.** When the event-store write fails (S3 outage, permissions), the event is lost: no retry, nothing in the dead-letter queue. Lineage has a gap for that event.

**Fix.** Let the failure reach `AbstractTask` (the message stays and is delivered again).

<a id="kd-6"></a>
### KD-6 · event-writer: the error-rate health check never counts a failed write (since July 2017)

**Technical.** `@Metered` sits on a private method, which Guice AOP cannot intercept, and the check reads a meter named after `SQSMessageWriterTask`.

**Functional effect.** As KD-2: `errorsPerSecondAverage` stays healthy while writes fail.

<a id="kd-7"></a>
### KD-7 · error-processor: every email goes to the first recipient (since September 2017)

**Technical.** For each configured recipient (`errorEmailRecipient`, comma-separated), the task writes the recipient into the incoming `MetaData` projections, a map that every email-queue message shares, so every message carries the first address (error-processor design open issue 6).

**Functional effect.** With two or more recipients, every error email goes to the first address and the others receive nothing. With one recipient there is no visible effect.

<a id="kd-8"></a>
### KD-8 · splitter: a split document can carry another document's control number (since June 2018)

**Technical.** `SplitterTask.processAllTransactions` routes the groups of one batch in parallel (one task per group on the shared executor, since February 2018). Each group writes its `documentControlNumber`, `interchangeControlReferenceNumber`, `ediId` and `integrationProfileId` into the **parent** `MetaData`'s projections (`SplitTransactionProcessor.enrichMetaData`, a plain `HashMap`), then copies that map for its child (`buildMetaData`). Two groups at once overwrite each other between the write and the copy, and the copy can throw `ConcurrentModificationException`.

**Functional effect.** A split document can go downstream with another document's control number, so its booking, SI or event is matched to the wrong document; or the whole batch fails and is retried. Only batches with more than one group are affected. The disabled test routed 20 groups in parallel, 50 times: 900 of the 1000 split documents had another group's number.

**Fix (checked).** Each group works on its own deep copy of the parent. `new MetaData.Builder(metaData).setProjections(..)` is not enough, because it still writes into the shared map. With a per-group `MetaData.parseJson(metaData.toJsonString())` the test passed twice.

<a id="kd-9"></a>
### KD-9 · splitter: the whole partner document is logged at INFO (since September 2023)

**Technical.** `SplitterTask.process` logs `"String content of file {} is {}"` with the full document at INFO (commit `c4583ff4`).

**Functional effect.** Every partner document (bookings and shipping instructions, with names, addresses and cargo details) is copied into the service log and kept for the log's retention, outside the workspace's access control. Large files also make the log large.

**Fix (checked).** Log the file name only, or the content at DEBUG.

<a id="kd-10"></a>
### KD-10 · splitter: a document is both retried and routed (since November 2018)

**Technical.** `SplitTransactionProcessor.validate`, for a document that needs no splitting, catches the authorization check's exception, hands it to the error handler (retry after 300 s, or error queue), then falls through to `return true`, so `SplitterTask` also routes it. The splitting path correctly returns `false`. Found by the splitter pre-review.

**Functional effect.** When Network Services fails during that check (or anything else throws there), the document reaches the next service at once **and** again after the retry, or it is routed while a failure `MetaData` goes to the error queue. The result is duplicate bookings or events downstream, and a failure event for a document that was delivered.

**Fix (checked).** `return false` after `handleError` in the `catch`.

<a id="kd-11"></a>
### KD-11 · splitter: the error-rate health check never turns unhealthy (since April 2017)

**Technical.** As [KD-2](#kd-2): `SplitterApplication` gives the check `name(SplitterTask.class, MESSAGES_FAILED_METRIC)`, but the meters that are marked belong to the classes that declare the `@Metered` methods: the shared `ErrorHandler` (batch failures) and `SplitErrorHandler` (per-document failures). Found by the splitter pre-review.

**Functional effect.** `errorsPerSecondAverage` stays healthy however many files fail. File processing is not affected.

**Fix (checked).** Give the check a meter that the handlers mark. The test passed with `name(ErrorHandler.class, …)`; a full fix also counts `SplitErrorHandler`'s failures, for example with one absolute meter name for both.

<a id="kd-12"></a>
### KD-12 · transformer: control-number retries do not reset (since March 2019)

**Technical.** `ControlNumberSequenceProvider` (a singleton) keeps its conflict-retry counter in a field and resets it only after a successful save. When a reservation conflicts 11 times it throws without resetting, so the counter stays at 10.

**Functional effect.** After one reservation gives up (heavy contention between instances), every later reservation in that instance fails at its first conflict, and those documents fail, until the instance restarts.

**Fix (checked).** Reset the counter when giving up (or count retries in a local variable).

<a id="kd-13"></a>
### KD-13 · transformer: a permanent failure builds the parameters twice (since May 2018)

**Technical.** `TransformerErrorHandler.getErrorQueue` calls `TransformationParamsProvider.get` again to find the context's error queue. Building the parameters reads the document and, for an outbound document, writes a supplement and reserves a control number. The golden file `outbound-map-missing` shows both supplements.

**Functional effect.** One more workspace read per failure; an outbound failure leaves a second supplement and skips a control number.

**Fix (checked).** Look the error queue up from the routing by context code (`getTargetQueues`) and the applicable transformation's direction, without building the parameters.

<a id="kd-14"></a>
### KD-14 · transformer: unknown routing ends in a NullPointerException (since May 2018)

**Technical.** In the same method, when building the parameters throws, the exception is printed and the null parameters are dereferenced.

**Functional effect.** The message is never handled: it is delivered again and again until the queue's redrive.

**Fix (checked).** Fall back to the configured error queue (`super.getErrorQueue`).

<a id="kd-15"></a>
### KD-15 · ingestor: one unreadable message drops the events of its whole batch (since July 2018)

**Technical.** `IngestorTask.process` reads every message of the received batch inside one `try`/`catch (Exception)`; the first message that is not an SNS envelope with a list of events ends the loop, the exception is logged ("Exception in Ingestor") and nothing is indexed. `execute` then deletes every message.

**Functional effect.** The events of the other messages of that batch (up to 10 messages, each with one service call's events) are never indexed: those workflows miss steps in transaction tracking.

**Fix (checked).** Read each message in its own `try`/`catch` and skip (log) the unreadable one.

<a id="kd-16"></a>
### KD-16 · ingestor: a batch delivered again duplicates its event documents (since July 2018)

**Technical.** `ElasticSearchEventRepository.submitEvent` adds each event to the bulk request as `new Index.Builder(json).build()`, without an id, so Elasticsearch generates one each time. The aggregates are upserts by workflow id and are not affected.

**Functional effect.** When a batch is delivered again (its delete failed, or processing took longer than the visibility timeout), every event document of it is indexed a second time.

**Fix (checked).** Index each event with its `eventId` as the document id (`.id(event.getEventId())`).

<a id="kd-17"></a>
### KD-17 · ingestor: a batch Elasticsearch could not take is deleted (since July 2018)

**Technical.** `ElasticSearchEventRepository.submit` retries 3 times, then throws a `RecoverableException`; `IngestorTask.process` catches every exception and only logs it, so `execute` goes on to delete every message of the batch. Its own "Message will reappear" branch (no delete) is never reached. Found by the ingestor pre-review.

**Functional effect.** During an Elasticsearch outage longer than the three tries (about a second), every batch received is lost for tracking.

**Fix (checked).** Let the `RecoverableException` out of `process` (rethrow it before the general `catch`), so `execute` leaves the batch on the queue for redelivery.

<a id="kd-18"></a>
### KD-18 · distributor: every failure loops until the redrive (since March 2021)

**Technical.** `DistributorTask` passes `ImmutableMap.of(PICK_UP_QUEUE, …)` to the shared `ErrorHandler`, which adds `pickupQueue` itself and merges both into an `ImmutableMap`; the duplicate key throws `IllegalArgumentException` after the error-queue message and the annotations were written, so no failure event is published and the task never deletes the message (seen in the golden test's two error cases).

**Functional effect.** A failing delivery is retried on every receive until the queue's redrive moves it to the DLQ, writing one error-queue message and one annotations object each time, and its lineage gets no failure event.

**Fix (checked).** The task passes no `pickupQueue` token to the handler (`ImmutableMap.of()`), or the shared fix `buildKeepingLast()` (see KD-1).

<a id="kd-19"></a>
### KD-19 · distributor: the error-rate health check never turns unhealthy (since June 2017)

**Technical.** `DistributorApplication` gives `ErrorThresholdHealthCheck` the meter `DistributorTask.messages-failed`; the failure meter is the shared `ErrorHandler`'s `@Metered` method's, registered as `ErrorHandler.messages-failed`.

**Functional effect.** `errorsPerSecondAverage` is always healthy.

**Fix (checked).** Give the check `name(ErrorHandler.class, MESSAGES_FAILED_METRIC)`.

<a id="kd-20"></a>
### KD-20 · distributor: not idempotent on redelivery (since June 2017)

**Technical.** The delivered file name usually holds `[randomSequence]` and a timestamp, and the zip's workspace key a `UUID.randomUUID()`; a message processed again (after a crash between the delivery and archive copies, or a visibility timeout) gets new ones.

**Functional effect.** The partner may receive a second file for one document; an orphan zip stays in the workspace.

**Fix.** Not small (the names are random by design): derive the random part from the message (for example its workflow id). No disabled test; listed for completeness (review summary §4).

<a id="kd-21"></a>
### KD-21 · distributor: an unparsable pickup message loops until the redrive (since June 2017)

**Technical.** `DistributorTask.process` parses the `MetaData` before its `try`, so a parse failure skips the error handler and reaches `AbstractTask`, which only logs "Message will reappear". Found by the distributor pre-review.

**Functional effect.** A malformed message (truncated JSON, a stray text) is received until the queue's redrive moves it to the DLQ; no event, no error-queue message.

**Fix.** Not decided: parse inside the `try` and send the raw message to the error queue (the error handler needs a `MetaData`). No disabled test.

<a id="kd-22"></a>
### KD-22 · distributor-rest: one cached OAuth token for every subscription (since March 2021, security)

**Technical.** `distributorrest.auth.AuthClient` is a singleton with one `token` field; `getToken` returns it whatever the subscription's OAuth URL, and only a 401 from a subscriber makes `newToken` replace it.

**Functional effect.** The bearer token one subscriber's OAuth endpoint issued is sent to other subscribers' endpoints. Recorded in the golden test (`shared-token`). Not raised with QA (Arijit 2026-11-20, [A5](closed-items.md#a5)).

**Fix (checked).** Cache a token per OAuth URL (a map keyed by `oauthRequest.getOAuthUrl()`).

<a id="kd-23"></a>
### KD-23 · distributor-rest: a FAILURE answer is retried as recoverable (since March 2021)

**Technical.** `RestServiceClient.post` throws `NonRecoverableException` for a non-SUCCESS answer inside its `try`, whose `catch (Exception)` wraps it as `RecoverableException`; the task's `catch (NonRecoverableException | IOException)` never sees it, and the recoverable exception escapes to `AbstractTask` (message not deleted).

**Functional effect.** A document the subscriber rejects is posted again on every receive until the redrive; no error-queue message.

**Fix (checked).** `catch (NonRecoverableException e) { throw e; }` before the general `catch`.

<a id="kd-24"></a>
### KD-24 · distributor-rest: a handled failure loops (since March 2021, as KD-18)

**Technical.** The task passes `ImmutableMap.of(PICK_UP_QUEUE, …)` to the shared `ErrorHandler`, which adds `pickupQueue` again; the failure event's `ImmutableMap` fails on the duplicate key after the error-queue message was sent.

**Functional effect.** No failure event; the message comes back until the redrive.

**Fix (checked, with KD-23's).** The task passes no `pickupQueue` token (`ImmutableMap.of()`).

<a id="kd-25"></a>
### KD-25 · distributor-rest: a webhook that is not the first action (since March 2021)

**Technical.** `RequestBuilder.build` loops over the actions and, for the `EDI_WEBHOOK` one, reads `subscription.getActions().get(0).getActionParameters()`: the first action's parameters.

**Functional effect.** With another action first, the request has no endpoint (`null?connectionId=null`): nothing is posted and the message loops until the redrive.

**Fix (checked).** Read `action.getActionParameters()`.

<a id="kd-26"></a>
### KD-26 · distributor-rest: an unparsable pickup message loops until the redrive (since March 2021, as KD-21)

**Technical.** `DistributorTask.process` parses the `MetaData` before its `try`, and a message without projections throws a `NullPointerException` at the subscription-id lookup; neither is caught, so `AbstractTask` only logs "Message will reappear". Found by the distributor-rest pre-review.

**Fix.** As KD-21: not decided. No disabled test.

<a id="kd-27"></a>
### KD-27 · watermill-publisher (with pi-statusevents-out-processor): non-ASCII characters published garbled (seen in QA since at least October 2026)

**Technical.** pi-statusevents-out-processor (mercury-services, on cloud-sdk) stores the status event with the cloud-sdk `S3StorageClient` as UTF-8 bytes (`text/plain; charset=UTF-8`), but the XML declares `encoding="ISO-8859-1"`. watermill-publisher reads it with `getContent(bucket, key, ISO_8859_1)` and parses the string, so each two-byte UTF-8 character becomes two Latin-1 characters. Seen on the QA objects of 2026-11-19 and in QA's published messages of 2026-10-22 ([fixtures](runtime/fixtures/qa-se-watermill/README.md)).

**Functional effect.** e2open receives `Tokyo, TÃ´kyÃ´ [Tokyo], JAPAN` instead of `Tokyo, Tôkyô [Tokyo], JAPAN`, in the location literals and in the original XML.

**Fix.** In the producer: write the document as ISO-8859-1 bytes, or declare UTF-8. Changing watermill-publisher to read UTF-8 would garble the documents that really are ISO-8859-1. The golden test records today's output; no disabled test here.

<a id="kd-28"></a>
### KD-28 · watermill-publisher: one failed redrive run ends the redrive (since May 2021)

**Technical.** `ListenerManager.start` schedules `DeadLetterService` with `scheduleAtFixedRate`; a run that throws is never run again (the scheduled future completes exceptionally), and `run` catches nothing.

**Fix (checked).** Catch and log the failure in `DeadLetterService.run`.

<a id="kd-29"></a>
### KD-29 · watermill-publisher: every reconnect leaves one more cleaner thread (since May 2021)

**Technical.** Each new stream creates a `ResponseObserver`, whose constructor starts a non-daemon `CleanerThread` with an endless loop; nothing stops the previous one. Each also reads the queue's `VisibilityTimeout` once.

**Fix (checked).** Stop the old observer's cleaner (interrupt it and end its loop) when the client creates a new observer.

<a id="kd-30"></a>
### KD-30 · watermill-publisher: a failed delete on an ack drops the other acks (since May 2021)

**Technical.** `ResponseObserver.onNext` calls `deleteMessage` without a guard; the exception on the gRPC callback cancels the call, `onError` resets the stream and clears every pending ack.

**Functional effect.** The other events of that stream are not deleted and are published again after the visibility timeout.

**Fix (checked).** Catch and log a failed delete in `onNext`; only that message comes back.

<a id="kd-31"></a>
### KD-31 · watermill-publisher: a poison message cycles between the DLQ and the pickup queue (since May 2021)

**Technical.** The redrive moves the body only, every 30 minutes, with no attempt count; the queue's redrive policy sends it back to the DLQ after 5 receives.

**Fix.** Not decided (an attempt counter, or a cap on moves). No disabled test.

<a id="kd-32"></a>
### KD-32 · watermill-publisher: the stream-reset flag is not volatile (since May 2021)

**Technical.** `StatusEventGrpcClient.resetStream` is written by the gRPC callback thread and read by the listener thread without `volatile`. The listener may not see a reset and keep calling `onNext` on a completed stream. Not reproducible in a test. (The migration made the observer field volatile, which the new shutdown drain reads; the flag is left as it is.)

**Fix.** Declare the flag `volatile` (or `AtomicBoolean`).

<a id="kd-33"></a>
### KD-33 · watermill-publisher: a startup wiring failure surfaces as a NullPointerException (since May 2021)

**Technical.** `WatermillPubApplication.run` catches any exception from `Guice.createInjector`, prints its stack trace to stderr and continues with a null injector. Found by the pre-review. The same failures existed in v1 (an unknown parameter name, no region).

**Fix.** Let the exception propagate.
