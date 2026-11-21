#!/usr/bin/env bash
# Collects test 6's outputs (all READ, except that receive-message hides each message for 30 s):
#  1. every message in bk_inbound_dlq and file_delivery_dlq -> out/msg/<queue>-<MessageId>.json (body) + receipts.tsv
#  2. each object a message names (fileName, and the supplement in projections.transformationSupplement if any)
#     -> out/obj/<key with / replaced by __> plus its head-object headers (.head.json)
#  3. every lineage event stored under our marked roots -> out/events/
# Usage: bash collect.sh   (run in rt6/, with $P set to the profile)
set -u
P=${P:-642960533737_INTTRA2-QATeam}
B=https://sqs.us-east-1.amazonaws.com/642960533737
mkdir -p out/msg out/obj out/events
: > out/receipts.tsv
for q in bk_inbound_dlq file_delivery_dlq; do
  for i in 1 2 3 4 5; do                              # several calls: one receive returns at most 10, often fewer
    aws sqs receive-message --profile $P --region us-east-1 --queue-url $B/inttra2_qa_sqs_$q \
      --max-number-of-messages 10 --visibility-timeout 30 --wait-time-seconds 2 \
      --query 'Messages[].[MessageId,ReceiptHandle,Body]' --output json > out/recv.json
    python -I - "$q" <<'EOF'
import json, sys
q = sys.argv[1]
for mid, rh, body in json.load(open("out/recv.json")) or []:
    open(f"out/msg/{q}-{mid}.json", "w", encoding="utf-8").write(body)
    open("out/receipts.tsv", "a").write(f"{q}\t{mid}\t{rh}\n")
EOF
  done
done
ls out/msg | wc -l
# objects named by the messages
python -I - > out/keys.txt <<'EOF'
import json, os
for f in sorted(os.listdir("out/msg")):
    m = json.load(open(os.path.join("out/msg", f), encoding="utf-8"))
    print(m["fileName"])
    s = m.get("projections", {}).get("transformationSupplement")
    if s: print(s)
EOF
while read k; do
  n=${k//\//__}
  aws s3api get-object --profile $P --bucket inttra2-qa-workspace --key "$k" "out/obj/$n" \
    --query '{ContentType:ContentType,ContentLength:ContentLength,Metadata:Metadata}' --output json > "out/obj/$n.head.json"
done < <(tr -d '\r' < out/keys.txt)      # Python on Windows writes CRLF: strip the CR or every key gets NoSuchKey
# events under our roots (event-writer stores eventstore/<UTC date>/<root>/<event>.json)
for r in $(cut -d/ -f1 out/keys.txt | sort -u); do
  aws s3 cp --profile $P --recursive --only-show-errors "s3://inttra2-qa-workspace/eventstore/2026-11-20/$r/" "out/events/$r/"
done
find out/events -type f | wc -l
