#!/usr/bin/env bash
# Runtime test 8: run one distributor build against QA and feed it its marked messages.
# Usage: bash run.sh <v1|v2>   (from the rt8 folder; credentials exported by the caller)
set -u
b=$1
S=$(pwd)
B=https://sqs.us-east-1.amazonaws.com/642960533737
Q=$B/inttra2_qa_sqs_file_delivery_dlq
E=$B/inttra2_qa_sqs_subscription_errors_dlq
P=642960533737_INTTRA2-QATeam
count() { aws sqs get-queue-attributes --profile $P --region us-east-1 --queue-url $1 \
  --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible \
  --query 'Attributes.[ApproximateNumberOfMessages,ApproximateNumberOfMessagesNotVisible]' --output text | tr '\t' ' '; }

echo "$(date -u +%T) queues before: pickup $(count $Q), errors $(count $E)"
while IFS=$'\t' read -r src dst; do
  aws s3api copy-object --profile $P --copy-source "inttra2-qa-workspace/$src" --bucket inttra2-qa-workspace \
    --key "$dst" --query CopyObjectResult.ETag --output text >> copies-$b.out
done < <(tr -d '\r' < copies-$b.tsv)
echo "$(date -u +%T) workspace copies: $(grep -c . copies-$b.out)"

cp distributor.yaml.$b distributor.yaml
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(cygpath -w $S/start-java.ps1)" -Service distributor \
  -Jar distributor-$b.jar -Log run-$b -Xmx 512m > launcher-run-$b.out 2>&1
for i in $(seq 1 90); do grep -q "Started oejs.Server" run-$b.log 2>/dev/null && break; sleep 1; done
echo "$(date -u +%T) started"

n=0
while IFS= read -r line; do
  n=$((n + 1))
  printf '%s' "$line" > msg.tmp
  aws sqs send-message --profile $P --region us-east-1 --queue-url $Q \
    --message-body "file://$(cygpath -w $S/msg.tmp)" --query MessageId --output text >> sent-$b.txt
  sleep 3
done < <(tr -d '\r' < messages-$b.jsonl)
echo "$(date -u +%T) sent $n"

for i in $(seq 1 30); do [ "$(count $Q)" = "0 0" ] && break; sleep 5; done
sleep 10
echo "$(date -u +%T) queues after: pickup $(count $Q), errors $(count $E)"

pid=$(tr -d '\r\n' < run-$b.pid)
t0=$(date +%s%3N)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(cygpath -w $S/send-ctrl-c.ps1)" -ProcessId $pid > /dev/null
powershell.exe -NoProfile -Command "\$x=Get-Process -Id $pid -ErrorAction SilentlyContinue; if(\$x){[void]\$x.WaitForExit(60000)}"
echo "$(date -u +%T) stopped in $(( $(date +%s%3N) - t0 )) ms; ERROR lines: $(grep -c 'ERROR' run-$b.log); copies logged: $(grep -c 'has been copied to' run-$b.log)"
