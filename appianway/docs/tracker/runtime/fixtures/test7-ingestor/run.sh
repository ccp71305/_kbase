#!/usr/bin/env bash
# Runtime test 7: run one ingestor build against QA and feed it its marked messages.
# Usage: bash run.sh <v1|v2>   (from the rt7 folder; credentials exported by the caller)
set -u
b=$1
S=$(pwd)
Q=https://sqs.us-east-1.amazonaws.com/642960533737/inttra2_qa_sqs_ingest_dlq
P=642960533737_INTTRA2-QATeam
count() { aws sqs get-queue-attributes --profile $P --region us-east-1 --queue-url $Q \
  --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible \
  --query 'Attributes.[ApproximateNumberOfMessages,ApproximateNumberOfMessagesNotVisible]' --output text | tr '\t' ' '; }

echo "$(date -u +%T) queue before: $(count)"
cp ingestor.yaml.$b ingestor.yaml
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(cygpath -w $S/start-java.ps1)" -Service ingestor \
  -Jar ingestor-$b.jar -Log run-$b -Xmx 512m > launcher-run-$b.out 2>&1
for i in $(seq 1 90); do grep -q "Started oejs.Server" run-$b.log 2>/dev/null && break; sleep 1; done
echo "$(date -u +%T) started: $(grep -c 'Listener .* starting' run-$b.log) listener(s)"

n=0
while IFS= read -r line; do
  n=$((n + 1))
  printf '%s' "$line" > msg.tmp
  aws sqs send-message --profile $P --region us-east-1 --queue-url $Q \
    --message-body "file://$(cygpath -w $S/msg.tmp)" --query MessageId --output text >> sent-$b.txt
done < <(tr -d '\r' < messages-$b.jsonl)
echo "$(date -u +%T) sent $n"

for i in $(seq 1 60); do
  c=$(count)
  [ "$c" = "0 0" ] && break
  sleep 5
done
sleep 15
echo "$(date -u +%T) queue after: $(count)"

pid=$(tr -d '\r\n' < run-$b.pid)
t0=$(date +%s%3N)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(cygpath -w $S/send-ctrl-c.ps1)" -ProcessId $pid > /dev/null
powershell.exe -NoProfile -Command "\$x=Get-Process -Id $pid -ErrorAction SilentlyContinue; if(\$x){[void]\$x.WaitForExit(60000)}"
echo "$(date -u +%T) stopped in $(( $(date +%s%3N) - t0 )) ms; ERROR lines: $(grep -c 'ERROR' run-$b.log); Elastic failures: $(grep -c -E 'Request Failed|Elastic Service call failed' run-$b.log)"
