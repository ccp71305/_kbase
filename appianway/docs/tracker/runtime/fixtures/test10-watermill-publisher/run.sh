#!/usr/bin/env bash
# Runtime test 10: run one watermill-publisher build locally against QA, with a local TLS stand-in for Watermill
# (nothing is published to e2open), feed it the two marked QA status events, then stop it with Ctrl+C.
# Usage: bash run.sh <v1|v2>   (from the rt10 folder; QA credentials exported by the caller)
set -u
b=$1
S=$(pwd)
Q=https://sqs.us-east-1.amazonaws.com/642960533737/inttra2_qa_sqs_rest_delivery_dlq
P=642960533737_INTTRA2-QATeam
count() { aws sqs get-queue-attributes --profile $P --region us-east-1 --queue-url $Q \
  --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible \
  --query 'Attributes.[ApproximateNumberOfMessages,ApproximateNumberOfMessagesNotVisible]' --output text | tr '\t' ' '; }

echo "$(date -u +%T) queue before: $(count)"

# the local Watermill (TLS on localhost:18443), recording into wm-<build>.txt
java -cp watermill-publisher-$b.jar LocalWatermill.java 18443 wm-cert.pem wm-key.pem wm-$b.txt > wm-$b.out 2>&1 &
wm=$!
for i in $(seq 1 30); do grep -q listening wm-$b.out 2>/dev/null && break; sleep 1; done

# the service; its JVM trusts the stand-in's certificate (a copy of the JDK CAs plus that one certificate)
cp watermill-publisher.yaml.$b watermill-publisher.yaml
t0=$(date +%s%3N)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(cygpath -w $S/start-java.ps1)" -Service watermill-publisher \
  -Jar watermill-publisher-$b.jar -Log run-$b -Xmx 512m \
  -JvmOpts "-Djavax.net.ssl.trustStore=$(cygpath -w $S/truststore.jks);-Djavax.net.ssl.trustStorePassword=changeit" \
  > launcher-$b.out 2>&1
for i in $(seq 1 90); do grep -q -E "Started oejs.Server|Exception in thread" run-$b.log 2>/dev/null && break; sleep 1; done
echo "$(date -u +%T) started in $(( $(date +%s%3N) - t0 )) ms: $(grep -c 'Listener .* starting' run-$b.log) listener(s)"
curl -s -m 30 -o hc-$b.json -w "$(date -u +%T) health check HTTP %{http_code} in %{time_total}s\n" http://localhost:18090/admin/healthcheck
python -c "import json;d=json.load(open('hc-$b.json'));[print('  ',k,v.get('healthy')) for k,v in d.items()]"

for z in z9 z7; do
  aws sqs send-message --profile $P --region us-east-1 --queue-url $Q \
    --message-body "file://$(cygpath -w $S/msg-$b-$z.json)" --query MessageId --output text >> sent-$b.txt
done
echo "$(date -u +%T) sent 2"

for i in $(seq 1 30); do
  c=$(count)
  [ "$c" = "0 0" ] && break
  sleep 3
done
sleep 10
echo "$(date -u +%T) queue after: $(count); events at the local Watermill: $(grep -c '  event ' wm-$b.txt)"

pid=$(tr -d '\r\n' < run-$b.pid)
t0=$(date +%s%3N)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(cygpath -w $S/send-ctrl-c.ps1)" -ProcessId $pid > /dev/null
powershell.exe -NoProfile -Command "\$x=Get-Process -Id $pid -ErrorAction SilentlyContinue; if(\$x){[void]\$x.WaitForExit(60000)}"
echo "$(date -u +%T) stopped in $(( $(date +%s%3N) - t0 )) ms; ERROR lines: $(grep -c 'ERROR' run-$b.log); clients closed: $(grep -c 'Closing' run-$b.log)"
kill $wm 2>/dev/null
