#!/usr/bin/env bash
# Runtime test 10, busy stop: Ctrl+C while Watermill's acks are still pending.
# Usage: bash run-busy.sh <v1|v2> <busy|noack> <ack delay ms; -1 = never>
#   (from the rt10 folder; QA credentials exported by the caller)
set -u
b=$1; v=$2; delay=$3
S=$(pwd)
Q=https://sqs.us-east-1.amazonaws.com/642960533737/inttra2_qa_sqs_rest_delivery_dlq
P=642960533737_INTTRA2-QATeam
count() { aws sqs get-queue-attributes --profile $P --region us-east-1 --queue-url $Q \
  --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible \
  --query 'Attributes.[ApproximateNumberOfMessages,ApproximateNumberOfMessagesNotVisible]' --output text | tr '\t' ' '; }
L=$v-$b

echo "$(date -u +%T) [$L] queue before (visible in-flight): $(count)"
java -cp watermill-publisher-$b.jar LocalWatermill.java 18443 wm-cert.pem wm-key.pem wm-$L.txt $delay > wm-$L.out 2>&1 &
wm=$!
for i in $(seq 1 30); do grep -q listening wm-$L.out 2>/dev/null && break; sleep 1; done

cp watermill-publisher.yaml.$b watermill-publisher.yaml
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(cygpath -w $S/start-java.ps1)" -Service watermill-publisher \
  -Jar watermill-publisher-$b.jar -Log run-$L -Xmx 512m \
  -JvmOpts "-Djavax.net.ssl.trustStore=$(cygpath -w $S/truststore.jks);-Djavax.net.ssl.trustStorePassword=changeit" \
  > launcher-$L.out 2>&1
for i in $(seq 1 90); do grep -q "Started oejs.Server" run-$L.log 2>/dev/null && break; sleep 1; done
echo "$(date -u +%T) [$L] started"

for z in z9 z7; do
  aws sqs send-message --profile $P --region us-east-1 --queue-url $Q \
    --message-body "file://$(cygpath -w $S/$v-$b-$z.json)" --query MessageId --output text >> sent-$L.txt
done
for i in $(seq 1 60); do [ "$(grep -c ' received ' wm-$L.out)" -ge 2 ] && break; sleep 0.5; done
echo "$(date -u +%T) [$L] both events at the local Watermill, acks pending ($delay ms): sending Ctrl+C"

pid=$(tr -d '\r\n' < run-$L.pid)
t0=$(date +%s%3N)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(cygpath -w $S/send-ctrl-c.ps1)" -ProcessId $pid > /dev/null
powershell.exe -NoProfile -Command "\$x=Get-Process -Id $pid -ErrorAction SilentlyContinue; if(\$x){[void]\$x.WaitForExit(60000)}"
echo "$(date -u +%T) [$L] stopped in $(( $(date +%s%3N) - t0 )) ms"
echo "  stand-in: received $(grep -c ' received ' wm-$L.out), acked $(grep -c ' acked ' wm-$L.out), could not ack $(grep -c 'could not ack' wm-$L.out)"
echo "  service: acks handled $(grep -c 'Response for messageId' run-$L.log); drain warning $(grep -c 'still in progress or not acked' run-$L.log); clients closed $(grep -c 'Closing' run-$L.log); ERROR lines other than the missing _dlq_dlq $(grep ERROR run-$L.log | grep -v -c -E 'does not exist|_dlq_dlq')"
echo "$(date -u +%T) [$L] queue right after the stop: $(count)"
kill $wm 2>/dev/null
sleep 35
echo "$(date -u +%T) [$L] queue 35 s later (after the 30 s visibility timeout): $(count)"
