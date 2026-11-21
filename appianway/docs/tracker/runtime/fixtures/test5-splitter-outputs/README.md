# Test 5 outputs: splitter's real messages, ready as transformer inputs (2026-11-20)

← [Runtime index](../../README.md) · [Test 5 log](../../splitter.md#test-5) · [Tracker home](../../../README.md)

What the local splitter runs of [test 5](../../splitter.md#test-5) sent, stored and published on QA, kept for the next services. The objects they name **stay in the QA workspace** (kept, per Arijit), so the routed messages can be sent to transformer's borrowed pickup DLQ as they are.

| Folder / file | What |
|---|---|
| [`inputs/`](inputs/) | The four splitter inputs: dispatcher's real `MetaData` from the QA traces with a marked root (`wi01124532-rt-sp-{v1,v2}-{bf,bc}`) |
| [`routed/`](routed/) | The six routed `MetaData` (v1 and new build × 1 booking + 2 confirmations), as read from `inttra2_qa_sqs_transformer_inbound_dlq`. **`v2-*` are transformer inputs** (context `requestBooking` / `confirmBooking`) |
| [`documents/`](documents/) | The objects the routed messages name, with their headers: the kept booking (`text/plain`, partner metadata) and the two split confirmations (`application/octet-stream`, 53,607 bytes, no metadata). QA test data |
| [`events/`](events/) | The ten lineage events stored by QA's event-writer (2 per booking run, 3 per confirmation run) |
| [`compare.txt`](compare.txt), [`compare-events.txt`](compare-events.txt) | The comparison results |
| [`splitter.local.properties`](splitter.local.properties) | The local configuration (borrowed queues, port 18085) |

| Routed message (new build) | Names object | For |
|---|---|---|
| `routed/v2-bf-BK3_Request_MinMSC.json` | `inttra2-qa-workspace/wi01124532-rt-sp-v2-bf/BK3_Request_MinMSC` (467 B, IFTMBF from `CU2100`) | transformer inbound (booking request) |
| `routed/v2-bc-434766ec-….json` | `inttra2-qa-workspace/wi01124532-rt-sp-v2-bc/434766ec-72f9-4cc8-9dd5-3f074b675671` (53,607 B, IFTMBC from `CA2000`) | transformer inbound (booking confirmation) |
| `routed/v2-bc-4fedaefb-….json` | `inttra2-qa-workspace/wi01124532-rt-sp-v2-bc/4fedaefb-a845-4cb8-9728-2857b30b312b` (53,607 B) | transformer inbound (booking confirmation) |

QA's own downstream results for the same two files (transformer, booking, distributor, awbridgeob) are in [qa-iftmbf-bk3-minmsc](../qa-iftmbf-bk3-minmsc/README.md) and [qa-iftmbc-2docs-sa-confirm-max](../qa-iftmbc-2docs-sa-confirm-max/README.md): the expected results for transformer's test.
