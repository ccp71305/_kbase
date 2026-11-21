# QA trace: one IFTMBC file with two booking confirmations (2026-11-19)

← [Runtime index](../../README.md) · [Tracker home](../../../README.md)

A real QA run, read back from QA (read only) on 2026-11-20: a carrier file with **two** confirmations in one interchange, so splitter's **splitting path** (two split documents written to the workspace, routed one by one). QA test data, not production content. Companion of the single-booking trace [qa-iftmbf-bk3-minmsc](../qa-iftmbf-bk3-minmsc/README.md); production's batch shapes are in [prod-samples.md](../prod-samples.md).

| | |
|---|---|
| Inbound file | `inttra2-qa-inbound-pickup/301_IFTMBC/20261119/carriers/CA2000/BK3_SAConfirm_Max_996677102.txt` (115,526 bytes, 00:08:03 UTC) |
| Sender | carrier `CA2000` |
| Content | one interchange `20231103R01`, two `IFTMBC:D:99B:UN:2.0` messages, no UNG; copy: [`BK3_SAConfirm_Max_996677102.qa-inbound.edi`](BK3_SAConfirm_Max_996677102.qa-inbound.edi) |
| Root workflow id | `d77b8868-1c3a-4527-b6bb-9dbb302ba6f2` |
| Workspace copy (dispatcher) | `inttra2-qa-workspace/d77b8868-1c3a-4527-b6bb-9dbb302ba6f2/a7d191de-7a1b-469d-8ecd-a79f0b37efef`, metadata `originalfilename`, `xlogid`, `inftpfilepickuptime` |
| Split documents | two, written by splitter under the same root (their keys are in the two splitter `startWorkflow` events) |
| Events | `inttra2-qa-workspace/eventstore/2026-11-19/d77b8868-1c3a-4527-b6bb-9dbb302ba6f2/` (50), copied to [`events/`](events/) |

## Inputs per service

| Service | Input (its `pickUpMessage`) | Pickup queue | Drop-off queue | From event |
|---|---|---|---|---|
| dispatcher | [`input-dispatcher.json`](input-dispatcher.json) | `inttra2_qa_sqs_dispatcher_pu` | `inttra2_qa_sqs_splitter_pu` | `events/dispatcher-closeRun-f4e3aeef-85bc-4356-a817-f164f41af30b.json` |
| splitter | [`input-splitter.json`](input-splitter.json) | `inttra2_qa_sqs_splitter_pu` | `` | `events/splitter-closeRun-841390cc-b784-43c0-962f-e088e58b0789.json` |
| splitter-split-document | [`input-splitter-split-document.json`](input-splitter-split-document.json) | `inttra2_qa_sqs_splitter_pu` | `inttra2_qa_sqs_transformer_inbound` | `events/splitter-closeRun-86e34ff5-8c78-4e9b-87dd-bab8b7668e43.json` |
| transformer-inbound | [`input-transformer-inbound.json`](input-transformer-inbound.json) | `inttra2_qa_sqs_transformer_inbound` | `inttra2_qa_sqs_bk_inbound` | `events/transformer-closeRun-9e2b5794-dfc0-4c96-b5ea-3ab08e37c5c3.json` |
| transformer-outbound | [`input-transformer-outbound.json`](input-transformer-outbound.json) | `inttra2_qa_sqs_transformer_inbound` | `inttra2_qa_sqs_file_delivery` | `events/transformer-closeRun-f5be2fbb-33b4-4d2f-87ec-11ab7437ffdb.json` |
| distributor | [`input-distributor.json`](input-distributor.json) | `inttra2_qa_sqs_file_delivery` | `` | `events/distributor-closeRun-a78e513e-7e46-43ee-92e0-0ee243a23179.json` |
| awbridgeob | [`input-awbridgeob.json`](input-awbridgeob.json) | `inttra2_qa_sqs_bridgeob_pu` | `` | `events/awbridgeob-closeRun-3fbef599-c6cb-43cd-8d62-1d65d8cde0dc.json` |

## The whole run, in order

| Time (UTC) | Component | Event | Workflow ← parent | Pickup | Drop-off | Other tokens |
|---|---|---|---|---|---|---|
| 00:08:04.07 | dispatcher | closeRun startWorkflow | `d77b8868` ← `d77b8868` | `inttra2_qa_sqs_dispatcher_pu` | `inttra2_qa_sqs_splitter_pu` | fileType, inboundS3FileName, inftpfilepickuptime, mftId, originalFileName, originalFileSiz |
| 00:08:04.25 | splitter | closeRun startWorkflow | `bc95ae83` ← `d77b8868` | `inttra2_qa_sqs_splitter_pu` | `inttra2_qa_sqs_transformer_inbound` |  |
| 00:08:04.39 | splitter | closeRun startWorkflow | `1519b31d` ← `d77b8868` | `inttra2_qa_sqs_splitter_pu` | `inttra2_qa_sqs_transformer_inbound` |  |
| 00:08:04.41 | splitter | closeRun closeWorkflow | `d77b8868` ← `d77b8868` | `inttra2_qa_sqs_splitter_pu` | `` | ediId, integrationProfileId, interchangeControlReferenceNumber |
| 00:08:05.14 | booking-inbound | startRun  | `1519b31d` ← `d77b8868` | `inttra2_qa_sqs_bk_inbound` | `` | pickupMessage |
| 00:08:05.14 | transformer | closeRun  | `1519b31d` ← `d77b8868` | `inttra2_qa_sqs_transformer_inbound` | `inttra2_qa_sqs_bk_inbound` | timeTakenForStructuralValidation, timeTakenForTransformation |
| 00:08:05.17 | transformer | closeRun  | `bc95ae83` ← `d77b8868` | `inttra2_qa_sqs_transformer_inbound` | `inttra2_qa_sqs_bk_inbound` | timeTakenForStructuralValidation, timeTakenForTransformation |
| 00:08:05.18 | booking-inbound | startRun  | `bc95ae83` ← `d77b8868` | `inttra2_qa_sqs_bk_inbound` | `` | pickupMessage |
| 00:08:05.25 | booking-service-doConfirm | startRun  | `1519b31d` ← `d77b8868` | `inttra2_qa_sqs_bk_inbound` | `` |  |
| 00:08:05.30 | booking-outbound | startRun  | `1519b31d` ← `d77b8868` | `inttra2_qa_sqs_bk_inbound` | `` |  |
| 00:08:05.30 | booking-service-doConfirm | closeRun  | `1519b31d` ← `d77b8868` | `` | `` | bookingId, carrierId, carrierName, carrierReferenceNumber, channel, inttraReferenceNumber, |
| 00:08:05.32 | booking-inbound | closeRun  | `1519b31d` ← `d77b8868` | `` | `` | ignored |
| 00:08:05.32 | booking-service-doConfirm | startRun  | `bc95ae83` ← `d77b8868` | `inttra2_qa_sqs_bk_inbound` | `` |  |
| 00:08:05.35 | booking-outbound | closeRun  | `1519b31d` ← `d77b8868` | `` | `` | bookerId, bookerName, bookingId, carrierId, carrierName, carrierReferenceNumber, channel,  |
| 00:08:05.36 | booking-subscription | startRun  | `1519b31d` ← `d77b8868` | `inttra2_qa_sqs_bk_inbound` | `` |  |
| 00:08:05.37 | booking-outbound | startRun  | `bc95ae83` ← `d77b8868` | `inttra2_qa_sqs_bk_inbound` | `` |  |
| 00:08:05.37 | booking-service-doConfirm | closeRun  | `bc95ae83` ← `d77b8868` | `` | `` | bookingId, carrierId, carrierName, carrierReferenceNumber, channel, inttraReferenceNumber, |
| 00:08:05.39 | booking-outbound | closeRun  | `bc95ae83` ← `d77b8868` | `` | `` | bookerId, bookerName, bookingId, carrierId, carrierName, carrierReferenceNumber, channel,  |
| 00:08:05.42 | booking-subscription | startRun  | `bc95ae83` ← `d77b8868` | `inttra2_qa_sqs_bk_inbound` | `` |  |
| 00:08:05.43 | booking-inbound | closeRun  | `bc95ae83` ← `d77b8868` | `` | `` | ignored |
| 00:08:07.45 | booking-subscription | closeRun  | `bc95ae83` ← `d77b8868` | `` | `` | carrierReferenceNumber, inttraReferenceNumber, subscription, subscriptionActions, subscrip |
| 00:08:07.46 | booking-subscription | startRun  | `bc95ae83` ← `d77b8868` | `inttra2_qa_sqs_bk_inbound` | `` |  |
| 00:08:07.62 | booking-subscription | closeRun  | `bc95ae83` ← `d77b8868` | `` | `inttra2_qa_sqs_transformer_inbound` | carrierReferenceNumber, integrationProfileFormatId, inttraReferenceNumber, outboundJsonFil |
| 00:08:07.63 | booking-subscription | startRun  | `bc95ae83` ← `d77b8868` | `inttra2_qa_sqs_bk_inbound` | `` |  |
| 00:08:07.68 | booking-subscription | closeRun  | `1519b31d` ← `d77b8868` | `` | `` | carrierReferenceNumber, inttraReferenceNumber, subscription, subscriptionActions, subscrip |
| 00:08:07.69 | booking-subscription | startRun  | `1519b31d` ← `d77b8868` | `inttra2_qa_sqs_bk_inbound` | `` |  |
| 00:08:07.79 | booking-subscription | closeRun  | `bc95ae83` ← `d77b8868` | `` | `inttra2_qa_sqs_transformer_inbound` | carrierReferenceNumber, integrationProfileFormatId, inttraReferenceNumber, outboundJsonFil |
| 00:08:07.80 | booking-notifcation | startRun  | `bc95ae83` ← `d77b8868` | `inttra2_qa_sqs_bk_inbound` | `` |  |
| 00:08:07.82 | booking-notifcation | closeRun  | `bc95ae83` ← `d77b8868` | `` | `` | notifyMeEmails, pushNotificationEmails |
| 00:08:07.87 | booking-subscription | closeRun  | `1519b31d` ← `d77b8868` | `` | `inttra2_qa_sqs_transformer_inbound` | carrierReferenceNumber, integrationProfileFormatId, inttraReferenceNumber, outboundJsonFil |
| 00:08:07.88 | booking-subscription | startRun  | `1519b31d` ← `d77b8868` | `inttra2_qa_sqs_bk_inbound` | `` |  |
| 00:08:07.98 | transformer | closeRun  | `bc95ae83` ← `d77b8868` | `inttra2_qa_sqs_transformer_inbound` | `inttra2_qa_sqs_file_delivery` | timeTakenForStructuralValidation, timeTakenForTransformation, transformationSupplement |
| 00:08:08.06 | booking-subscription | closeRun  | `1519b31d` ← `d77b8868` | `` | `inttra2_qa_sqs_transformer_inbound` | carrierReferenceNumber, integrationProfileFormatId, inttraReferenceNumber, outboundJsonFil |
| 00:08:08.07 | booking-notifcation | startRun  | `1519b31d` ← `d77b8868` | `inttra2_qa_sqs_bk_inbound` | `` |  |
| 00:08:08.15 | distributor | closeRun closeWorkflow | `bc95ae83` ← `d77b8868` | `inttra2_qa_sqs_file_delivery` | `` | s3DeliveryFileName |
| 00:08:08.24 | booking-notifcation | closeRun  | `1519b31d` ← `d77b8868` | `` | `` | notifyMeEmails, pushNotificationEmails |
| 00:08:08.24 | transformer | closeRun  | `bc95ae83` ← `d77b8868` | `inttra2_qa_sqs_transformer_inbound` | `inttra2_qa_sqs_file_delivery` | timeTakenForStructuralValidation, timeTakenForTransformation, transformationSupplement |
| 00:08:08.26 | transformer | closeRun  | `1519b31d` ← `d77b8868` | `inttra2_qa_sqs_transformer_inbound` | `inttra2_qa_sqs_file_delivery` | timeTakenForStructuralValidation, timeTakenForTransformation, transformationSupplement |
| 00:08:08.40 | distributor | closeRun closeWorkflow | `1519b31d` ← `d77b8868` | `inttra2_qa_sqs_file_delivery` | `` | s3DeliveryFileName |
| 00:08:08.43 | transformer | closeRun  | `1519b31d` ← `d77b8868` | `inttra2_qa_sqs_transformer_inbound` | `inttra2_qa_sqs_file_delivery` | timeTakenForStructuralValidation, timeTakenForTransformation, transformationSupplement |
| 00:08:08.44 | distributor | closeRun closeWorkflow | `bc95ae83` ← `d77b8868` | `inttra2_qa_sqs_file_delivery` | `` | s3DeliveryFileName |
| 00:08:08.59 | distributor | closeRun closeWorkflow | `1519b31d` ← `d77b8868` | `inttra2_qa_sqs_file_delivery` | `` | s3DeliveryFileName |
| 00:08:09.13 | awbridgeob | closeRun  | `bc95ae83` ← `d77b8868` | `inttra2_qa_sqs_bridgeob_pu` | `` | ftpArchiveDeliveryFileName |
| 00:08:09.26 | awbridgeob | closeRun  | `1519b31d` ← `d77b8868` | `inttra2_qa_sqs_bridgeob_pu` | `` | ftpArchiveDeliveryFileName |
| 00:08:09.36 | awbridgeob | closeRun  | `bc95ae83` ← `d77b8868` | `inttra2_qa_sqs_bridgeob_pu` | `` | ftpDeliveryFileName |
| 00:08:09.37 | awbridgeob | closeRun  | `bc95ae83` ← `d77b8868` | `inttra2_qa_sqs_bridgeob_pu` | `` | ftpArchiveDeliveryFileName |
| 00:08:09.50 | awbridgeob | closeRun  | `1519b31d` ← `d77b8868` | `inttra2_qa_sqs_bridgeob_pu` | `` | ftpArchiveDeliveryFileName |
| 00:08:09.51 | awbridgeob | closeRun  | `1519b31d` ← `d77b8868` | `inttra2_qa_sqs_bridgeob_pu` | `` | ftpDeliveryFileName |
| 00:08:09.63 | awbridgeob | closeRun  | `bc95ae83` ← `d77b8868` | `inttra2_qa_sqs_bridgeob_pu` | `` | ftpDeliveryFileName |
| 00:08:09.73 | awbridgeob | closeRun  | `1519b31d` ← `d77b8868` | `inttra2_qa_sqs_bridgeob_pu` | `` | ftpDeliveryFileName |

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
