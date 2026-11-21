#!/usr/bin/env bash
# Deletes only this test's messages (workflow ids wi01124532-rt-wmp-...) from the borrowed queue; anything else is
# left untouched (made visible again at once).
set -u
Q=https://sqs.us-east-1.amazonaws.com/642960533737/inttra2_qa_sqs_rest_delivery_dlq
P=642960533737_INTTRA2-QATeam
for round in 1 2 3; do
  aws sqs receive-message --profile $P --region us-east-1 --queue-url $Q --max-number-of-messages 10 \
    --wait-time-seconds 5 --visibility-timeout 30 --output json > received.json
  python -I - <<'PYEOF' > handles.txt
import json
d = json.load(open('received.json')) if open('received.json').read().strip() else {}
for m in d.get('Messages', []):
    ours = 'wi01124532-rt-wmp-' in m['Body']
    print(('OURS ' if ours else 'OTHER ') + m['ReceiptHandle'])
PYEOF
  [ -s handles.txt ] || break
  while read kind handle; do
    if [ "$kind" = OURS ]; then
      aws sqs delete-message --profile $P --region us-east-1 --queue-url $Q --receipt-handle "$handle" && echo "deleted one of ours"
    else
      aws sqs change-message-visibility --profile $P --region us-east-1 --queue-url $Q --receipt-handle "$handle" \
        --visibility-timeout 0 && echo "left one other message"
    fi
  done < handles.txt
done
rm -f received.json handles.txt
