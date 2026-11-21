# Runtime verification: distributor

← [Runtime index](README.md) · [Tracker home](../README.md)

<a id="summary"></a>
## In functional terms

distributor delivers each outbound document to the partner's folder in the outbound bucket and archives a copy, with workflow metadata on both. **The new build delivers exactly what the old one does:** for a real CONTRL FA and a real X12 301 confirmation to CU2100 (and the FA without its optional metadata), both builds delivered and archived byte-identical objects with the same content type and user metadata, under keys of the same shape from QA's real Network Services settings, with the same lineage events; and the same as QA's own deliveries of those documents on 2026-11-19. QA's FTP bridge picked up the new build's deliveries as it does v1's. A delivery without optional metadata keeps the empty keys, as v1 (the shared fix of this PR). Starts, healthy, stops on Ctrl+C in 1.5 s.

How the builds are built and run: [how-to](../howto/build-and-run-a-service-locally.md). Approved by Arijit 2026-11-20: real deliveries into QA's outbound bucket ("ok to use outbound bucket, we are not changing anything and it is QA only"). Tools and outputs: [fixtures/test8-distributor/](fixtures/test8-distributor/).

<a id="experiment"></a>
## Before the test: null user metadata on an S3 copy (2026-11-20)

Design open issue 3: distributor's delivered objects get the outbound integration profile format id, context code and outbound EDI id as user metadata even when they are null. What S3 stores then, with each SDK:

| # | Time (UTC) | Action | Resource | Result |
|---|---|---|---|---|
| 1 | 20:3x | **WRITE** `s3api put-object` of a 19-byte text object | `inttra2-qa-workspace/wi01124532-rt-dist-nullmeta/source` | stored |
| 2 | 20:3x | **WRITE** SDK v1 REPLACE copy with `{workflowId, contextCode=null, outboundEdiId=null}`, as `S3WorkspaceService.copyObjectWithMetaDate` ([NullMetaV1.java](fixtures/test8-distributor/NullMetaV1.java), run on ingestor's v1 jar) | `…/v1-copy` | done |
| 3 | 20:3x | **WRITE** SDK 2.x REPLACE copy with the same metadata and `application/octet-stream`, as cloud-sdk `S3StorageClient.copyObject` ([NullMetaV2.java](fixtures/test8-distributor/NullMetaV2.java), on ingestor's new jar) | `…/v2-copy` | done |
| 4 | 20:3x | `s3api head-object` of both (read) | | v1: `ContentType application/octet-stream`, metadata `{workflowid, contextcode: "", outboundediid: ""}`; **v2: `application/octet-stream`, metadata `{workflowid}` only** |

Conclusion ([F31](../findings.md#f31)): SDK v1 stores a null value as empty, SDK 2.x drops the key; the content type is the same. The shared adapter now writes null as `""`.

```bash
P=642960533737_INTTRA2-QATeam; B=inttra2-qa-workspace; K=wi01124532-rt-dist-nullmeta
aws s3api put-object --profile $P --bucket $B --key $K/source --body "$(cygpath -w $S/rt8/src.txt)" --content-type text/plain   # W
eval "$(aws configure export-credentials --profile $P --format env)"; export AWS_REGION=us-east-1
java -cp ingestor-v1.jar NullMetaV1.java $B $K/source $K/v1-copy      # W, SDK v1 (in the v1 jar through shared)
java -cp ingestor-v2.jar NullMetaV2.java $B $K/source $K/v2-copy      # W, SDK 2.x (in the new jar through cloud-sdk-aws)
aws s3api head-object --profile $P --bucket $B --key $K/v1-copy --query '{ContentType:ContentType,Metadata:Metadata}'   # R
```

`java -cp <jar> <File>.java` runs one source file against the jar's classes (Java 11+ source-file mode), so each copy is made by the same SDK version as the build it stands for. `head-object` returns the stored headers: `Metadata` holds the user metadata (`x-amz-meta-*`, keys in lower case).

**Left in QA:** the three objects under `wi01124532-rt-dist-nullmeta/`.

<a id="test-8"></a>
## Test 8 (2026-11-20, approved by Arijit)

v1 = `e90a355a` (feature tip, distributor on SDK v1); new = `007d96cd` (PR head). Pickup `inttra2_qa_sqs_file_delivery_dlq`, errors `inttra2_qa_sqs_subscription_errors_dlq` (both borrowed, empty before and after), workspace `inttra2-qa-workspace`, **outbound `inttra2-qa-outbound-delivery` (real deliveries, approved)**, event topic and Network Services: QA. Local properties: [distributor.local.properties](fixtures/test8-distributor/distributor.local.properties).

Inputs ([make-inputs.py](fixtures/test8-distributor/make-inputs.py)): the two real QA distributor inputs (CONTRL FA, IPF 2366; X12 301, IPF 1709) and the FA without `contextCode` and `outboundEdiId`; workflow ids marked `wi01124532-rt-dist-<build>-<case>`, each on its own marked copy of QA's real document (201 B, 41,985 B).

| # | Time (UTC) | Action | Resource | Result |
|---|---|---|---|---|
| 1 | 20:5x | Pre-checks (read) | the 2 borrowed DLQs; the 2 real documents | 0/0, 0/0; both exist |
| 2 | 20:5x–21:01 | Built the jars | build worktree: full build at `007d96cd` (BUILD SUCCESS, 11:08 min), v1 at `e90a355a` | 92 MB each; yaml differs only in the logger lines |
| 3 | 21:02:41–21:03:32 | **WRITE** v1: 3 `copy-object` to marked roots, started, 3 `send-message`, Ctrl+C ([run.sh](fixtures/test8-distributor/run.sh)) | workspace, `file_delivery_dlq`, outbound bucket | 6 objects delivered and archived; 0 ERROR lines; queues 0/0; stopped in 1.8 s |
| 4 | 21:03:43–21:04:32 | **WRITE** new build: the same | | 6 objects; 0 ERROR lines; 4 clients closed; stopped in 1.5 s (the pickup in-flight count lagged: 0/0 a minute later) |
| 5 | 21:0x | Collected (read: `head-object`, `s3 cp`, the event store) ([collect.py](fixtures/test8-distributor/collect.py)) | outbound bucket, `eventstore/2026-11-20/<root>/` | [outputs](fixtures/test8-distributor/outputs/) |
| 6 | 21:1x | Compared | | below |

**v1 vs the new build** ([compare.txt](fixtures/test8-distributor/compare.txt), [compare-events.txt](fixtures/test8-distributor/compare-events.txt)):

| Output | Result |
|---|---|
| Delivered and archived objects (6 per build) | **byte-identical** bodies; `Content-Type: application/octet-stream` both; user metadata identical; keys of the same shape (`customers/CU2100/outbound/CONTRL/CONTRL_<time>_<random>.txt`, `…/outbound/301/KOTAHI802435IFTMBC2<time>_<random>.txt`, archives under `outbound_archive/<format>/<date>/`) |
| The delivery without optional metadata | new build: `contextcode: ""`, `outboundediid: ""`, as v1 ([F31](../findings.md#f31) fixed) |
| distributor's `closeWorkflow` events (3 per build) | identical (times, ids, random names normalized) |
| QA's FTP bridge (awbridgeob) | picked up all 6 objects of each build (6 events each): the downstream hand-off works with the new build's deliveries |

**The new build vs QA's own deliveries** of the same documents on 2026-11-19 (keys from QA's events: `CONTRL_20261119175538165_9025705928.txt`, `KOTAHI802435IFTMBC220261119000808008_3254350241.txt`): body, content type and user metadata **identical** (workflow ids mapped), keys of the same shape.

**Result of test 8: passed.**

**Left in QA:** 12 delivered objects (6 per build) under `customers/CU2100/outbound*/` in `inttra2-qa-outbound-delivery`, and what the FTP bridge delivered from them to the QA FTP folders; 6 marked workspace copies; the events under the 6 marked roots. Queues: empty.

