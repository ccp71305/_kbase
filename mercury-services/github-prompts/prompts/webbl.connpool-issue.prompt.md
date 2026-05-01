---
name: webbl-connpool-issue
description: finding root cause and fix for webbl connection pool issue
argument-hint: "none"
agent: agent
model: Claude Opus 4.6 (copilot)
tools:
  - execute
  - read
  - edit
  - search
  - mcp-context-server/*
---
# Task instructions

## 1. Find the root cause and fix for the connection pool issue in webbl module

First review the document 2026-03-31-sqs-connection-pool-shutdown-investigation.md under webbl/docs/ to understand the initial analysis done
Next do a deep dive analysis and check production logs to find the root cause of the connection pool issue in webbl module.
There are 2 Tasks 
ARN: 
arn:aws:ecs:us-east-1:642960533737:task/ANEPRWEBSVC-001/25818ea1f08d4517b6e9fabc797df24c and 
arn:aws:ecs:us-east-1:642960533737:task/ANEPRWEBSVC-001/4ad01fb7680f4b48b43aa8f580c0df1f

Please do a deep analysis of the logs to find the issue, its root cause and possible fixes. 

I want to know:
1) What is invoking `ApacheHttpClient.close()` on the AWS SDK v2 HTTP client that is triggering `PoolingHttpClientConnectionManager.shutdown()` 
Why is this shutdown happening? Is it a bug in the AWS SDK v2 or is it some misconfiguration or misuse of the client in our code? Is it related to the lifecycle management of the SQS client in webbl module?
I understand that once shut down, **the connection pool can never be used again**. Every subsequent SQS `receiveMessage()` call will fail with this exception.

2) How often is this happening and what is the frequency of this issue in production (last 90 days)?

3) What is the impact of this issue in production? Is it causing any message processing failures or delays? Are we doing positive work ?

4) Why the `SqsClient` nor the `ApacheHttpClient` is registered with Dropwizard's lifecycle. They are "fire-and-forget" singletons with **no shutdown coordination** in webbl module? How can we remedy this?

5) The listenerManager.start() idiom in WebApplication.startListener() is common in other modules as well. 
Can you check existing visibility, booking, booking-bridge and oceanschedules modules. Do they have similar issues? Are they using the same idiom? If so, are they also not registering the SQS client with Dropwizard's lifecycle?

6) in your analysis, you said "For SQS listeners, the duplicate `submit()` on a single-thread executor gets queued" 
Where is the duplicate `submit()` happening?

7) in your analysis, what did you mean by DBConnections ?

8) In your analysis, you said "- `JVM_Xmx=384m` with ECS memory reservation of `256 MiB` — very tight; GC pauses can cause health check timeouts"
What is the proper remedy? explain your reasoning.

9) How can we handle the exception handling better ?

10) How can we Close `SqsClient`/`ApacheHttpClient` During Shutdown if it happens for valid reasons? 
What could be possible valid reasons?


## 2. Reported Exception
ERROR [2026-03-31 01:17:12.168] [id:] com.inttra.mercury.webbl.common.messaging.SQSClient: Exception while receiving messages from queue: https://sqs.us-east-1.amazonaws.com/642960533737/inttra2_pr_sqs_webbl_pdf_inbound

com.inttra.mercury.cloudsdk.messaging.exception.MessagingException: Unexpected SDK error while receiving from queue https://sqs.us-east-1.amazonaws.com/642960533737/inttra2_pr_sqs_webbl_pdf_inbound

  at com.inttra.mercury.cloudsdk.messaging.aws.impl.SqsMessagingClient.handleException(SqsMessagingClient.java:329)
  at com.inttra.mercury.cloudsdk.messaging.aws.impl.SqsMessagingClient.receiveMessages(SqsMessagingClient.java:234)
  at com.inttra.mercury.webbl.common.messaging.SQSClient.receiveMessage(SQSClient.java:56)
  at com.inttra.mercury.webbl.common.listener.SQSListener.pollAndExecute(SQSListener.java:79)
  at com.inttra.mercury.webbl.common.listener.SQSListener.startup(SQSListener.java:94)
  at java.base/java.util.concurrent.Executors$RunnableAdapter.call(Unknown Source)

  at java.base/java.util.concurrent.FutureTask.run(Unknown Source)

  at java.base/java.util.concurrent.ThreadPoolExecutor.runWorker(Unknown Source)

  at java.base/java.util.concurrent.ThreadPoolExecutor$Worker.run(Unknown Source)

  at java.base/java.lang.Thread.run(Unknown Source)

Caused by: java.lang.IllegalStateException: Connection pool shut down

  at org.apache.http.util.Asserts.check(Asserts.java:34)

  at org.apache.http.impl.conn.PoolingHttpClientConnectionManager.requestConnection(PoolingHttpClientConnectionManager.java:269)

  at software.amazon.awssdk.http.apache.internal.conn.ClientConnectionManagerFactory$DelegatingHttpClientConnectionManager.requestConnection(ClientConnectionManagerFactory.java:75)

  at software.amazon.awssdk.http.apache.internal.conn.ClientConnectionManagerFactory$InstrumentedHttpClientConnectionManager.requestConnection(ClientConnectionManagerFactory.java:57)

  at org.apache.http.impl.execchain.MainClientExec.execute(MainClientExec.java:176)

  at org.apache.http.impl.execchain.ProtocolExec.execute(ProtocolExec.java:186)

  at org.apache.http.impl.client.InternalHttpClient.doExecute(InternalHttpClient.java:185)

  at org.apache.http.impl.client.CloseableHttpClient.execute(CloseableHttpClient.java:83)

  at org.apache.http.impl.client.CloseableHttpClient.execute(CloseableHttpClient.java:56)

  at software.amazon.awssdk.http.apache.internal.impl.ApacheSdkHttpClient.execute(ApacheSdkHttpClient.java:72)

  at software.amazon.awssdk.http.apache.ApacheHttpClient.execute(ApacheHttpClient.java:259)

  at software.amazon.awssdk.http.apache.ApacheHttpClient.access$600(ApacheHttpClient.java:104)

  at software.amazon.awssdk.http.apache.ApacheHttpClient$1.call(ApacheHttpClient.java:236)

  at software.amazon.awssdk.http.apache.ApacheHttpClient$1.call(ApacheHttpClient.java:233)

  at software.amazon.awssdk.core.internal.util.MetricUtils.measureDurationUnsafe(MetricUtils.java:102)

  at software.amazon.awssdk.core.internal.http.pipeline.stages.MakeHttpRequestStage.executeHttpRequest(MakeHttpRequestStage.java:88)

  at software.amazon.awssdk.core.internal.http.pipeline.stages.MakeHttpRequestStage.execute(MakeHttpRequestStage.java:64)

  at software.amazon.awssdk.core.internal.http.pipeline.stages.MakeHttpRequestStage.execute(MakeHttpRequestStage.java:46)

  at software.amazon.awssdk.core.internal.http.pipeline.RequestPipelineBuilder$ComposingRequestPipelineStage.execute(RequestPipelineBuilder.java:206)

  at software.amazon.awssdk.core.internal.http.pipeline.RequestPipelineBuilder$ComposingRequestPipelineStage.execute(RequestPipelineBuilder.java:206)

  at software.amazon.awssdk.core.internal.http.pipeline.RequestPipelineBuilder$ComposingRequestPipelineStage.execute(RequestPipelineBuilder.java:206)

  at software.amazon.awssdk.core.internal.http.pipeline.RequestPipelineBuilder$ComposingRequestPipelineStage.execute(RequestPipelineBuilder.java:206)

  at software.amazon.awssdk.core.internal.http.pipeline.stages.ApiCallAttemptTimeoutTrackingStage.execute(ApiCallAttemptTimeoutTrackingStage.java:74)

  at software.amazon.awssdk.core.internal.http.pipeline.stages.ApiCallAttemptTimeoutTrackingStage.execute(ApiCallAttemptTimeoutTrackingStage.java:43)

  at software.amazon.awssdk.core.internal.http.pipeline.stages.Timeout

Also observed on the PDF queue:
```
ERROR [2026-03-31 15:40:03.475] [id:] com.inttra.mercury.cloudsdk.messaging.aws.impl.SqsMessagingClient:
  Unexpected SDK error while receiving from queue
  https://sqs.us-east-1.amazonaws.com/642960533737/inttra2_pr_sqs_webbl_zip_inbound

java.lang.IllegalStateException: Connection pool shut down
  at org.apache.http.util.Asserts.check(Asserts.java:34)
  at org.apache.http.impl.conn.PoolingHttpClientConnectionManager.requestConnection(...)
  at software.amazon.awssdk.http.apache.internal.conn.ClientConnectionManagerFactory$DelegatingHttpClientConnectionManager.requestConnection(...)
  at software.amazon.awssdk.http.apache.internal.conn.ClientConnectionManagerFactory$InstrumentedHttpClientConnectionManager.requestConnection(...)
  at org.apache.http.impl.execchain.MainClientExec.execute(...)
  at software.amazon.awssdk.http.apache.internal.impl.ApacheSdkHttpClient.execute(...)
  at software.amazon.awssdk.http.apache.ApacheHttpClient.execute(...)
  ... (AWS SDK pipeline stages)
```


Produce these : 

1) Update your findings and analysis in the document 2026-03-31-sqs-connection-pool-shutdown-investigation.md under webbl/docs/ with the answers to the above questions and any other relevant information you find during your investigation.


Follow these rules:

- Ask for clarification if the changes are not clear

- Create new session before starting in the session context. 

- Persist all important and necessary information in the session context as you proceed 

- before ending the session, mark the session as complete. 

This will help you and the next agent to have all the necessary information and context for any future work related to this task. 