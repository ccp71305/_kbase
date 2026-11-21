# QA trace: one IFTMBF booking through AppianWay (2026-11-19)

← [Runtime index](../../README.md) · [Tracker home](../../../README.md)

A real QA run, read back from QA (read only) on 2026-11-20, kept as the reference input and output for the runtime tests of splitter and the later services (transformer, distributor, ingestor, the booking consumers). Every service's lineage event holds, in `messages.pickUpMessage`, the exact message that service received, so each `input-*.json` below can be sent as-is (after giving it a marked root, see "How to reuse").

| | |
|---|---|
| Inbound file | `inttra2-qa-inbound-pickup/300_IFTMBF/20261119/customers/CU2100/BK3_Request_MinMSC` (467 bytes, uploaded 17:55:30 UTC) |
| Sender | `CU2100` (MFT id and EDI id), integration profile 4 |
| Content | one EDIFACT `IFTMBF:D:99B:UN:2.0` booking request (interchange `MIN1120000001`), copy: [`BK3_Request_MinMSC.qa-workspace.edi`](BK3_Request_MinMSC.qa-workspace.edi). The test-tool file `C:\Users\arijit.kundu\Downloads\BK3_Request_MinMSC.txt` is the same test case; only the generated `BGM` shipment id differs |
| Root workflow id | `a8511d88-4308-4774-9900-430aa0d7d1bc` |
| Workspace copy (dispatcher) | `inttra2-qa-workspace/a8511d88-4308-4774-9900-430aa0d7d1bc/7bf5abf8-b8e6-45fe-a6c1-2adee29bf4c7`, `text/plain`, metadata `originalfilename`, `xlogid`, `inftpfilepickuptime` |
| Split document | none written: a single valid document is kept (the routed `MetaData` names the original object), split workflow `1c224a22-5c3c-4dab-8cc3-a81b63b4db75` |
| Workspace objects of the whole run | `inttra2-qa-workspace/a8511d88-4308-4774-9900-430aa0d7d1bc/` (25 objects: transformer outputs, booking JSON, deliveries) |
| Events | `inttra2-qa-workspace/eventstore/2026-11-19/a8511d88-4308-4774-9900-430aa0d7d1bc/` (54), copied to [`events/`](events/) |
| Also seen in QA at the same time | an XML booking (`CU2100`, root `394902c3-dd9f-4d4b-9abd-91a2a19abe68`): the "no splitting" path |

## Inputs per service

| Service | Input (its `pickUpMessage`) | Pickup queue | Drop-off queue | From event |
|---|---|---|---|---|
| dispatcher | [`input-dispatcher.json`](input-dispatcher.json) | `inttra2_qa_sqs_dispatcher_pu` | `inttra2_qa_sqs_splitter_pu` | `events/dispatcher-closeRun-62168444-7648-49a4-a1c2-7f7fc499c592.json` |
| splitter | [`input-splitter.json`](input-splitter.json) | `inttra2_qa_sqs_splitter_pu` | `` | `events/splitter-closeRun-06a3b895-866c-43b6-ac02-f409edea71a5.json` |
| transformer-inbound | [`input-transformer-inbound.json`](input-transformer-inbound.json) | `inttra2_qa_sqs_transformer_inbound` | `inttra2_qa_sqs_bk_inbound` | `events/transformer-closeRun-adaf6daf-7d7a-48c1-a0cd-a4b24d233988.json` |
| transformer-outbound | [`input-transformer-outbound.json`](input-transformer-outbound.json) | `inttra2_qa_sqs_transformer_inbound` | `inttra2_qa_sqs_file_delivery` | `events/transformer-closeRun-d04c8386-3a0a-4381-ae21-428b95db5db5.json` |
| distributor | [`input-distributor.json`](input-distributor.json) | `inttra2_qa_sqs_file_delivery` | `` | `events/distributor-closeRun-ffd36acb-5545-43e6-a73b-cb23efc2d300.json` |
| awbridgeob | [`input-awbridgeob.json`](input-awbridgeob.json) | `inttra2_qa_sqs_bridgeob_pu` | `` | `events/awbridgeob-closeRun-f0133849-73d5-4adc-b806-8720174e5f53.json` |
| booking-inbound | (no event with an input) | | | |

## The whole run, in order

| Time (UTC) | Component | Event | Workflow ← parent | Pickup | Drop-off | Other tokens |
|---|---|---|---|---|---|---|
| 17:55:37.26 | dispatcher | closeRun startWorkflow | `a8511d88` ← `a8511d88` | `inttra2_qa_sqs_dispatcher_pu` | `inttra2_qa_sqs_splitter_pu` | fileType, inboundS3FileName, inftpfilepickuptime, mftId, originalFileName, originalFileSiz |
| 17:55:37.42 | splitter | closeRun startWorkflow | `1c224a22` ← `a8511d88` | `inttra2_qa_sqs_splitter_pu` | `inttra2_qa_sqs_transformer_inbound` |  |
| 17:55:37.46 | splitter | closeRun closeWorkflow | `a8511d88` ← `a8511d88` | `inttra2_qa_sqs_splitter_pu` | `` | ediId, integrationProfileId, interchangeControlReferenceNumber |
| 17:55:37.97 | booking-inbound | startRun  | `1c224a22` ← `a8511d88` | `inttra2_qa_sqs_bk_inbound` | `` | pickupMessage |
| 17:55:37.97 | transformer | closeRun  | `1c224a22` ← `a8511d88` | `inttra2_qa_sqs_transformer_inbound` | `inttra2_qa_sqs_bk_inbound` | timeTakenForStructuralValidation, timeTakenForTransformation |
| 17:55:38.09 | transformer | closeRun  | `f103b6aa` ← `1c224a22` | `inttra2_qa_sqs_transformer_inbound` | `inttra2_qa_sqs_file_delivery` | timeTakenForStructuralValidation, timeTakenForTransformation, transformationSupplement |
| 17:55:38.36 | distributor | closeRun closeWorkflow | `f103b6aa` ← `1c224a22` | `inttra2_qa_sqs_file_delivery` | `` | s3DeliveryFileName |
| 17:55:38.59 | booking-inbound | closeRun  | `1c224a22` ← `a8511d88` | `` | `` | ignored |
| 17:55:38.59 | booking-warning | startRun  | `1c224a22` ← `a8511d88` | `inttra2_qa_sqs_bk_inbound` | `` |  |
| 17:55:38.67 | booking-warning | closeRun  | `1c224a22` ← `a8511d88` | `` | `` | bookerId, bookerName, bookingId, carrierId, carrierName, carrierReferenceNumber, channel,  |
| 17:55:38.69 | booking-outbound | startRun  | `1c224a22` ← `a8511d88` | `inttra2_qa_sqs_bk_inbound` | `` |  |
| 17:55:38.70 | booking-outbound | closeRun  | `1c224a22` ← `a8511d88` | `` | `` | bookerId, bookerName, bookingId, carrierId, carrierName, carrierReferenceNumber, channel,  |
| 17:55:38.81 | booking-subscription | startRun  | `1c224a22` ← `a8511d88` | `inttra2_qa_sqs_bk_inbound` | `` |  |
| 17:55:39.10 | booking-subscription | closeRun  | `1c224a22` ← `a8511d88` | `` | `inttra2_qa_sqs_transformer_inbound` | integrationProfileFormatId, inttraReferenceNumber, outboundJsonFile, subscription, subscri |
| 17:55:39.12 | booking-subscription | startRun  | `1c224a22` ← `a8511d88` | `inttra2_qa_sqs_bk_inbound` | `` |  |
| 17:55:39.24 | booking-subscription | closeRun  | `1c224a22` ← `a8511d88` | `` | `inttra2_qa_sqs_transformer_inbound` | integrationProfileFormatId, inttraReferenceNumber, outboundJsonFile, subscription, subscri |
| 17:55:39.26 | booking-subscription | startRun  | `1c224a22` ← `a8511d88` | `inttra2_qa_sqs_bk_inbound` | `` |  |
| 17:55:39.31 | transformer | closeRun  | `1c224a22` ← `a8511d88` | `inttra2_qa_sqs_transformer_inbound` | `inttra2_qa_sqs_file_delivery` | timeTakenForStructuralValidation, timeTakenForTransformation, transformationSupplement |
| 17:55:39.36 | transformer | closeRun  | `1c224a22` ← `a8511d88` | `inttra2_qa_sqs_transformer_inbound` | `inttra2_qa_sqs_file_delivery` | timeTakenForStructuralValidation, timeTakenForTransformation, transformationSupplement |
| 17:55:39.36 | transformer | closeRun  | `1c224a22` ← `a8511d88` | `inttra2_qa_sqs_transformer_inbound` | `inttra2_qa_sqs_file_delivery` | timeTakenForStructuralValidation, timeTakenForTransformation, transformationSupplement |
| 17:55:39.45 | transformer | closeRun  | `1c224a22` ← `a8511d88` | `inttra2_qa_sqs_transformer_inbound` | `inttra2_qa_sqs_file_delivery` | timeTakenForStructuralValidation, timeTakenForTransformation, transformationSupplement |
| 17:55:39.49 | awbridgeob | closeRun  | `f103b6aa` ← `1c224a22` | `inttra2_qa_sqs_bridgeob_pu` | `` | ftpArchiveDeliveryFileName |
| 17:55:39.49 | booking-subscription | closeRun  | `1c224a22` ← `a8511d88` | `` | `inttra2_qa_sqs_transformer_inbound` | integrationProfileFormatId, inttraReferenceNumber, outboundJsonFile, subscription, subscri |
| 17:55:39.50 | booking-subscription | startRun  | `1c224a22` ← `a8511d88` | `inttra2_qa_sqs_bk_inbound` | `` |  |
| 17:55:39.51 | distributor | closeRun closeWorkflow | `1c224a22` ← `a8511d88` | `inttra2_qa_sqs_file_delivery` | `` | s3DeliveryFileName |
| 17:55:39.57 | distributor | closeRun closeWorkflow | `1c224a22` ← `a8511d88` | `inttra2_qa_sqs_file_delivery` | `` | s3DeliveryFileName |
| 17:55:39.62 | distributor | closeRun closeWorkflow | `1c224a22` ← `a8511d88` | `inttra2_qa_sqs_file_delivery` | `` | s3DeliveryFileName |
| 17:55:39.62 | transformer | closeRun  | `1c224a22` ← `a8511d88` | `inttra2_qa_sqs_transformer_inbound` | `inttra2_qa_sqs_file_delivery` | timeTakenForStructuralValidation, timeTakenForTransformation, transformationSupplement |
| 17:55:39.66 | distributor | closeRun closeWorkflow | `1c224a22` ← `a8511d88` | `inttra2_qa_sqs_file_delivery` | `` | s3DeliveryFileName |
| 17:55:39.74 | booking-subscription | closeRun  | `1c224a22` ← `a8511d88` | `` | `inttra2_qa_sqs_transformer_inbound` | integrationProfileFormatId, inttraReferenceNumber, outboundJsonFile, subscription, subscri |
| 17:55:39.75 | booking-subscription | startRun  | `1c224a22` ← `a8511d88` | `inttra2_qa_sqs_bk_inbound` | `` |  |
| 17:55:39.75 | distributor | closeRun closeWorkflow | `1c224a22` ← `a8511d88` | `inttra2_qa_sqs_file_delivery` | `` | s3DeliveryFileName |
| 17:55:39.92 | transformer | closeRun  | `1c224a22` ← `a8511d88` | `inttra2_qa_sqs_transformer_inbound` | `inttra2_qa_sqs_file_delivery` | timeTakenForStructuralValidation, timeTakenForTransformation, transformationSupplement |
| 17:55:39.96 | booking-subscription | closeRun  | `1c224a22` ← `a8511d88` | `` | `inttra2_qa_sqs_transformer_inbound` | integrationProfileFormatId, inttraReferenceNumber, outboundJsonFile, subscription, subscri |
| 17:55:39.97 | booking-notifcation | startRun  | `1c224a22` ← `a8511d88` | `inttra2_qa_sqs_bk_inbound` | `` |  |
| 17:55:39.98 | awbridgeob | closeRun  | `f103b6aa` ← `1c224a22` | `inttra2_qa_sqs_bridgeob_pu` | `` | ftpDeliveryFileName |
| 17:55:39.99 | booking-notifcation | closeRun  | `1c224a22` ← `a8511d88` | `` | `` | notifyMeEmails, pushNotificationEmails |
| 17:55:40.06 | distributor | closeRun closeWorkflow | `1c224a22` ← `a8511d88` | `inttra2_qa_sqs_file_delivery` | `` | s3DeliveryFileName |
| 17:55:40.13 | transformer | closeRun  | `1c224a22` ← `a8511d88` | `inttra2_qa_sqs_transformer_inbound` | `inttra2_qa_sqs_file_delivery` | timeTakenForStructuralValidation, timeTakenForTransformation, transformationSupplement |
| 17:55:40.26 | distributor | closeRun closeWorkflow | `1c224a22` ← `a8511d88` | `inttra2_qa_sqs_file_delivery` | `` | s3DeliveryFileName |
| 17:55:40.33 | awbridgeob | closeRun  | `1c224a22` ← `a8511d88` | `inttra2_qa_sqs_bridgeob_pu` | `` | ftpArchiveDeliveryFileName |
| 17:55:40.33 | awbridgeob | closeRun  | `1c224a22` ← `a8511d88` | `inttra2_qa_sqs_bridgeob_pu` | `` | ftpArchiveDeliveryFileName |
| 17:55:40.38 | awbridgeob | closeRun  | `1c224a22` ← `a8511d88` | `inttra2_qa_sqs_bridgeob_pu` | `` | ftpArchiveDeliveryFileName |
| 17:55:40.38 | awbridgeob | closeRun  | `1c224a22` ← `a8511d88` | `inttra2_qa_sqs_bridgeob_pu` | `` | ftpArchiveDeliveryFileName |
| 17:55:40.41 | awbridgeob | closeRun  | `1c224a22` ← `a8511d88` | `inttra2_qa_sqs_bridgeob_pu` | `` | ftpDeliveryFileName |
| 17:55:40.73 | awbridgeob | closeRun  | `1c224a22` ← `a8511d88` | `inttra2_qa_sqs_bridgeob_pu` | `` | ftpDeliveryFileName |
| 17:55:40.77 | awbridgeob | closeRun  | `1c224a22` ← `a8511d88` | `inttra2_qa_sqs_bridgeob_pu` | `` | ftpDeliveryFileName |
| 17:55:40.78 | awbridgeob | closeRun  | `1c224a22` ← `a8511d88` | `inttra2_qa_sqs_bridgeob_pu` | `` | ftpDeliveryFileName |
| 17:55:40.83 | awbridgeob | closeRun  | `1c224a22` ← `a8511d88` | `inttra2_qa_sqs_bridgeob_pu` | `` | ftpDeliveryFileName |
| 17:55:41.07 | awbridgeob | closeRun  | `1c224a22` ← `a8511d88` | `inttra2_qa_sqs_bridgeob_pu` | `` | ftpArchiveDeliveryFileName |
| 17:55:41.18 | awbridgeob | closeRun  | `1c224a22` ← `a8511d88` | `inttra2_qa_sqs_bridgeob_pu` | `` | ftpArchiveDeliveryFileName |
| 17:55:41.21 | awbridgeob | closeRun  | `1c224a22` ← `a8511d88` | `inttra2_qa_sqs_bridgeob_pu` | `` | ftpArchiveDeliveryFileName |
| 17:55:41.28 | awbridgeob | closeRun  | `1c224a22` ← `a8511d88` | `inttra2_qa_sqs_bridgeob_pu` | `` | ftpDeliveryFileName |
| 17:55:41.38 | awbridgeob | closeRun  | `1c224a22` ← `a8511d88` | `inttra2_qa_sqs_bridgeob_pu` | `` | ftpDeliveryFileName |

## Queues on the path (QA) and the borrowed DLQ for a local run

| Service | Reads | Writes | Borrowed for a local run |
|---|---|---|---|
| dispatcher | `inttra2_qa_sqs_dispatcher_pu` | `inttra2_qa_sqs_splitter_pu` | pickup `…dispatcher_pu_dlq`, out `…splitter_pu_dlq` (test 4) |
| splitter | `inttra2_qa_sqs_splitter_pu` | `inttra2_qa_sqs_transformer_inbound` (context `requestBooking`) | pickup `…splitter_pu_dlq`, out `…transformer_inbound_dlq` |
| transformer | `inttra2_qa_sqs_transformer_inbound` | `inttra2_qa_sqs_bk_inbound` (inbound), `inttra2_qa_sqs_file_delivery` (outbound) | `…transformer_inbound_dlq`, `…bk_inbound_dlq`, `…file_delivery_dlq` (to check they exist) |
| distributor | `inttra2_qa_sqs_file_delivery` | deliveries to the workspace, `inttra2_qa_sqs_bridgeob_pu` | `…file_delivery_dlq`, `…bridgeob_pu_dlq` (to check) |
| booking (watermill consumers) | `inttra2_qa_sqs_bk_inbound` | `inttra2_qa_sqs_transformer_inbound` (subscriptions) | `…bk_inbound_dlq` (to check) |

Errors of every service: `inttra2_qa_sqs_subscription_errors` (borrowed: `…_dlq`). Events: `inttra2_qa_sns_event` (real topic).

## How to reuse

1. Copy the input object to a marked root (`wi01124532-rt-<service>-v1/…`, `-v2/…`) with `s3api copy-object`, so test events do not join this booking's real lineage.
2. In the `input-*.json`, replace the workflow, parent and root ids and the `fileName` with the marked ones; keep the projections.
3. Send it to the borrowed pickup DLQ; compare the v1 and the new build's outputs with each other and with the QA run above.
