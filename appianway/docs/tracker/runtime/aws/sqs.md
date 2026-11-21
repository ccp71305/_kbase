# SQS commands

← [AWS commands index](README.md) · [Runtime index](../README.md)

Commands shown as run, in Git Bash on Windows, with AWS CLI v2. **R** = read only, **W** = changes something in AWS (each W agreed with Arijit before it ran). `P=642960533737_INTTRA2-QATeam`, options and helpers: [basics.md](basics.md).

<a id="4-sqs-queues-and-messages"></a>
## Queues and messages

```bash
aws sqs list-queues --profile $P --region us-east-1 --queue-name-prefix inttra2_qa_sqs_ --output text      # R
```
Lists queue URLs whose name starts with the prefix (at most 1000). The prefix keeps the answer to QA queues only.

```bash
aws sqs get-queue-attributes --profile $P --region us-east-1 --queue-url $B/inttra2_qa_sqs_dispatcher_pu \
    --attribute-names VisibilityTimeout ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible \
                      ReceiveMessageWaitTimeSeconds RedrivePolicy LastModifiedTimestamp \
    --query Attributes --output text                                                                     # R
```
Reads queue settings and counters without touching messages:
- `ApproximateNumberOfMessages`: waiting messages (visible);
- `ApproximateNumberOfMessagesNotVisible`: messages received by someone and not yet deleted ("in flight");
- `VisibilityTimeout`: how long a received message stays hidden before it comes back;
- `ReceiveMessageWaitTimeSeconds`: the queue's default long-poll wait, used when a receive sends no wait time (why the v1 health check takes 5 s);
- `RedrivePolicy`: where messages go after `maxReceiveCount` receives (the `_dlq`);
- `LastModifiedTimestamp`: when the queue's settings last changed (Unix seconds).

Used to check that a borrowed `_dlq` is empty before and after each test.

```bash
aws sqs send-message --profile $P --region us-east-1 --queue-url $B/inttra2_qa_sqs_splitter_pu_dlq \
    --message-body "file://$(cygpath -w $S/event-v1.json)" --query MessageId --output text                 # W
```
Puts one message on a queue. `--message-body file://<path>` reads the body from a file, which keeps JSON quoting intact. The answer is the new message's id. Optional, not used yet: `--delay-seconds`, `--message-attributes`.

```bash
aws sqs send-message-batch --profile $P --region us-east-1 --queue-url $B/inttra2_qa_sqs_dispatcher_pu_dlq     --entries "file://$(cygpath -w $S/burst-a.json)" --query 'length(Successful)' --output text           # W
```
Puts up to **10** messages on a queue in one call (the SQS limit per batch). `--entries` is a JSON list, here read from a file: `[{"Id": "burst01", "MessageBody": "…"}, …]`. `Id` only pairs each entry with its result in the answer and must be unique within the batch; it is not the message id. The answer has `Successful` and `Failed` lists; `length(Successful)` prints how many were accepted (10). Used for the dispatcher shutdown check (test 4b): 20 messages in two calls, so there is work in progress when the service is stopped.

```bash
aws sqs receive-message --profile $P --region us-east-1 --queue-url $B/inttra2_qa_sqs_email_outbound_dlq \
    --max-number-of-messages 10 --visibility-timeout 2 --wait-time-seconds 1 --message-attribute-names All \
    --query 'Messages[].[MessageId,Body]' --output text                                                   # R (peek)
```
Reads messages **without deleting them**. Only used on borrowed test queues that nothing else reads.
- `--max-number-of-messages` (1–10): at most this many per call.
- `--visibility-timeout 2`: hide the received messages for 2 s only, so they come back for the service under test. With `0`, SQS may return the **same** message several times in one answer, which is why 2 s is used.
- `--wait-time-seconds 1`: long poll up to 1 s.
- SQS answers from a sample of its servers, so on a queue with few messages one call may miss some. The peek is repeated a few times and the results de-duplicated by message id.
- `--message-attribute-names All` also returns message attributes such as `failedAttempts`.

Never used on a queue a QA service consumes: a receive there would hide a real message from the service.

```bash
aws sqs delete-message --profile $P --region us-east-1 --queue-url $Q --receipt-handle "$RH"            # W
```
Deletes one message. SQS deletes by **receipt handle**, not by message id: the handle is returned by the `receive-message` that received the message, and is only valid for that receive. So a delete is always "receive (with a visibility long enough), pick the right message by its body or id, delete it with that receive's handle". Used 2026-11-19 to remove only the stray `HEALTHCHECK` (`671fa523-…`) from the borrowed email queue.

```bash
aws sqs change-message-visibility --profile $P --region us-east-1 --queue-url $Q --receipt-handle "$RH" --visibility-timeout 0   # W (visibility only)
```
Changes how long a received message stays hidden. `0` returns it to the queue at once (used when the wrong message was received); a receive with `--visibility-timeout 900` hides a message for 15 minutes (used to keep the new build's email request away from the v1 run). The message itself is not changed.

<a id="dlq-precheck"></a>
## Checking several borrowed queues at once (test 6)

```bash
B=https://sqs.us-east-1.amazonaws.com/642960533737
for q in transformer_inbound_dlq bk_inbound_dlq subscription_errors_dlq file_delivery_dlq rest_delivery_dlq ce_validate_dlq os_inbound_dlq; do
  printf "%-28s " $q
  aws sqs get-queue-attributes --profile $P --region us-east-1 --queue-url $B/inttra2_qa_sqs_$q \
    --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible \
    --query 'Attributes.[ApproximateNumberOfMessages,ApproximateNumberOfMessagesNotVisible]' --output text      # R
done
```
Pre-check of the seven DLQs transformer borrows (pickup, booking, errors, file delivery, REST delivery, container-event validation, schedules): all exist, 0 visible and 0 in flight at 09:2x EST. `printf "%-28s "` prints the name left-aligned in 28 columns so the counts line up. A missing queue would answer `AWS.SimpleQueueService.NonExistentQueue`.

<a id="collect"></a>
## Collecting outputs and deleting only ours (test 6)

```bash
aws sqs receive-message --profile $P --region us-east-1 --queue-url $B/inttra2_qa_sqs_bk_inbound_dlq \
    --max-number-of-messages 10 --visibility-timeout 30 --wait-time-seconds 2 \
    --query 'Messages[].[MessageId,ReceiptHandle,Body]' --output json                                        # R (hides for 30 s)
aws sqs delete-message --profile $P --region us-east-1 --queue-url $B/inttra2_qa_sqs_bk_inbound_dlq --receipt-handle "$rh"   # W
```
Collecting and cleaning up the outputs (scripts `collect.sh`, `cleanup.sh` in [fixtures/test6-transformer/](../fixtures/test6-transformer/)). `receive-message` returns at most 10 messages per call (often fewer), so it is called several times; `--visibility-timeout 30` hides each received message for 30 s, so the next call returns others; `--wait-time-seconds 2` waits up to 2 s for messages (long polling). Nothing is deleted by a receive. `delete-message` needs the **receipt handle** of a receive, not the message id; the cleanup deletes only messages whose body has `"component":"transformer"` and a `wi01124532-rt-tf-` root, and makes any other one visible again with `change-message-visibility --visibility-timeout 0` (§4).
