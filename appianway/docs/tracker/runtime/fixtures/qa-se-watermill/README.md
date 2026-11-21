# QA status events for watermill-publisher (2026-11-19)

← [Runtime index](../../README.md)

Two real inputs of watermill-publisher in QA, 2026-11-19 00:13 UTC (root workflow `6c8ce0a6-3cd0-44f9-8488-40cd64cd7b6f`, a CargoWise container event fed by visibility-inbound-consumer). Found by tracing the workflow id across `inttra2-qa-lg-app-way` and `inttra2-qa-lg-pi`; read only.

| File | Workspace key | Workflow id | Event | Payload id (= proto message id) |
|---|---|---|---|---|
| `01b82791-….xml` | `6c8ce0a6-…/01b82791-162b-44da-897d-3d811f55210c` | `5ccd1070-723b-4236-9c88-ec80b6aa36a1` | Z9 Estimated Vessel Load at Transshipment Port | `0877cf6a-ad7c-4ebb-8067-a6f90c6056fd` |
| `076c812e-….xml` | `6c8ce0a6-…/076c812e-02e9-4f1f-ad5c-36a102cb0eb7` | `2fce3a25-9084-41ac-ba45-4ea1770f1520` | Z7 Estimated Vessel Departure at Transshipment Port | `097c0e74-3995-49fd-b9eb-9bd2a2ed1e99` |

**MetaData** (logged by `pi-statusevents-out-processor` `AppianwayIntegrator`, sent with `Json.toJsonString`): component `pi-statusevents-out-processor`, exit status `success`, bucket `inttra2-qa-workspace`, projections `outboundFormatId=129`, `eventProvider=CargoVisibility`, `contextCode=publishContainerEvent`, `CONTAINER_EVENT_ID=ce:<id>` (`ce:13ead06e-919c-4d20-94bc-407c0568580c`, `ce:98625dee-288f-4382-8142-32decb974425`). No `dxRoutes`: the published events have no tenants.

**Encoding.** The objects are **UTF-8 bytes** (written by the cloud-sdk `S3StorageClient` of pi-statusevents-out-processor, `text/plain; charset=UTF-8`) but declare `encoding="ISO-8859-1"`. watermill-publisher decodes them as ISO-8859-1, so `Tôkyô` is published as `TÃ´kyÃ´` (QA log of 2026-11-19: `Ã´`). Existing behaviour, [KD-27](../../../known-defects.md#kd-27).

Used by the golden test `WatermillPublisherWireCompatibilityTest` (copied byte for byte to `watermill-publisher/src/test/resources-functional/golden/`).
