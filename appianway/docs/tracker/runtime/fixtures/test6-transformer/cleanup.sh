#!/usr/bin/env bash
# Deletes test 6's messages from the borrowed DLQs (WRITE, agreed): receives each queue's messages and deletes only
# those whose body is transformer's MetaData for one of our marked roots; anything else is made visible again at once.
# Usage: bash cleanup.sh   (in rt6/, with $P set)
P=${P:-642960533737_INTTRA2-QATeam}
B=https://sqs.us-east-1.amazonaws.com/642960533737
for q in bk_inbound_dlq file_delivery_dlq transformer_inbound_dlq subscription_errors_dlq; do
  n=0; other=0
  for i in 1 2 3 4 5 6; do
    aws sqs receive-message --profile $P --region us-east-1 --queue-url $B/inttra2_qa_sqs_$q \
      --max-number-of-messages 10 --visibility-timeout 20 --wait-time-seconds 2 \
      --query 'Messages[].[ReceiptHandle,Body]' --output json > recv-clean.json
    while IFS=$'\t' read -r mine rh; do
      if [ "$mine" = yes ]; then
        aws sqs delete-message --profile $P --region us-east-1 --queue-url $B/inttra2_qa_sqs_$q --receipt-handle "$rh" && n=$((n+1))
      else
        aws sqs change-message-visibility --profile $P --region us-east-1 --queue-url $B/inttra2_qa_sqs_$q --receipt-handle "$rh" --visibility-timeout 0
        other=$((other+1))
      fi
    done < <(python -I -c "
import json
for rh, body in json.load(open('recv-clean.json')) or []:
    m = json.loads(body)
    mine = m.get('component') == 'transformer' and str(m.get('rootWorkflowId', '')).startswith('wi01124532-rt-tf-')
    print(('yes' if mine else 'no') + '\t' + rh)
" | tr -d '\r')
  done
  echo "$q: deleted $n, left (not ours) $other"
done
